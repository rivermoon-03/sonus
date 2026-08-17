from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from sonus.messages.registry import FEATURES
from sonus.messages.types import FeatureSpec
from sonus.protocol.framing import Frame


class DeviceError(Exception):
    """기기 기능 계층에서 발생하는 오류의 공통 기반."""


class UnsupportedFeatureError(DeviceError):
    pass


class UnsafeWriteError(DeviceError):
    pass


class WriteVerificationError(DeviceError):
    def __init__(self, key: str, requested: Any, observed: Any) -> None:
        super().__init__(
            f"write verification failed for {key}: "
            f"requested {requested!r}, observed {observed!r}"
        )
        self.key = key
        self.requested = requested
        self.observed = observed


class RestoreFailedError(DeviceError):
    pass


class _Session(Protocol):
    def request(
        self,
        data_type: int,
        payload: bytes = b"",
        *,
        response_matcher=None,
        response_required: bool = True,
    ) -> Frame | None: ...


@dataclass(frozen=True)
class FeatureResult:
    key: str
    label: str
    value: Any = None
    supported: bool = True
    writable: bool = False
    raw: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SonyXm6Device:
    def __init__(
        self,
        session: _Session,
        *,
        features: Mapping[str, FeatureSpec] = FEATURES,
    ) -> None:
        self._session = session
        self._features = dict(features)

    def _feature(self, key: str) -> FeatureSpec:
        try:
            return self._features[key]
        except KeyError as error:
            raise UnsupportedFeatureError(f"unknown feature: {key}") from error

    def get(self, key: str) -> FeatureResult:
        feature = self._feature(key)
        frame = self._session.request(
            feature.data_type,
            feature.request,
            # 같은 연결에는 동작 기록 알림 등이 섞이므로 명령과 항목을 함께 확인한다.
            response_matcher=lambda candidate: (
                candidate.data_type == feature.data_type
                and feature.matches_payload(candidate.payload)
            ),
        )
        assert frame is not None
        return FeatureResult(
            key=key,
            label=feature.label,
            value=feature.decode(frame.payload),
            writable=feature.writable,
            raw=frame.payload.hex(),
        )

    def get_many(self, keys: Iterable[str]) -> dict[str, FeatureResult]:
        results: dict[str, FeatureResult] = {}
        for key in keys:
            try:
                results[key] = self.get(key)
            except Exception as error:  # 항목 하나의 실패가 전체 상태 조회를 막지 않는다.
                feature = self._features.get(key)
                results[key] = FeatureResult(
                    key=key,
                    label=feature.label if feature else key,
                    supported=False,
                    writable=feature.writable if feature else False,
                    error=_error_code(error),
                )
        return results

    def snapshot(self) -> dict[str, FeatureResult]:
        return self.get_many(self._features)

    def capabilities(self) -> list[dict[str, Any]]:
        return [
            {
                "key": feature.key,
                "label": feature.label,
                "safety": feature.safety.value,
                "writable": feature.writable,
                "function_id": feature.function_id,
            }
            for feature in self._features.values()
        ]

    def set(self, key: str, value: Any) -> FeatureResult:
        feature = self._feature(key)
        if not feature.writable or feature.encoder is None:
            raise UnsafeWriteError(f"feature is read-only: {key}")
        response_required = (
            feature.write_response_command is not None
            and feature.write_response_type is not None
        )
        write_matcher = None
        if response_required:
            write_matcher = lambda candidate: (
                candidate.data_type == feature.data_type
                and feature.matches_write_payload(candidate.payload)
            )
        frame = self._session.request(
            feature.data_type,
            feature.encoder(value),
            response_matcher=write_matcher,
            response_required=response_required,
        )
        if frame is None:
            return FeatureResult(
                key=key,
                label=feature.label,
                value=value,
                writable=True,
            )
        return FeatureResult(
            key=key,
            label=feature.label,
            value=feature.decode_write(frame.payload),
            writable=True,
            raw=frame.payload.hex(),
        )

    def set_verified(self, key: str, value: Any) -> FeatureResult:
        self.set(key, value)
        observed = self.get(key)
        if observed.value != value:
            raise WriteVerificationError(key, value, observed.value)
        return observed

    @contextmanager
    def temporary_setting(self, key: str, value: Any) -> Iterator[FeatureResult]:
        original = self.get(key)
        try:
            changed = self.set_verified(key, value)
            yield changed
        finally:
            # 검증 중 예외가 나도 원복을 시도하고, 일시적인 실패에는 한 번 더 보낸다.
            last_error: Exception | None = None
            for _ in range(2):
                try:
                    self.set_verified(key, original.value)
                    break
                except Exception as error:
                    last_error = error
            else:
                raise RestoreFailedError(f"failed to restore {key}") from last_error


def _error_code(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, UnsupportedFeatureError):
        return "unsupported"
    if isinstance(error, ConnectionError):
        return "connection_closed"
    return error.__class__.__name__.removesuffix("Error").lower()
