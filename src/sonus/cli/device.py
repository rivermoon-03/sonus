from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

from sonus.device.xm6 import FeatureResult, SonyXm6Device
from sonus.messages.registry import DISCOVERY_FEATURES, FEATURES
from sonus.protocol.session import ProtocolSession
from sonus.transport.rfcomm import connect_with_retries as default_connect
from sonus.transport.sdp import find_rfcomm_channel as default_find_channel

DEFAULT_SERVICE_UUID = "956c7b26-d49a-4ba8-b03f-b17d393cb6e2"
STATUS_KEYS = (
    "model_name",
    "firmware_version",
    "battery",
    "codec",
    "connection_mode",
    "noise_control",
    "equalizer",
    "dsee",
    "auto_pause",
    "speak_to_chat",
    "auto_power_off",
    "voice_guidance",
    "voice_guidance_volume",
    "le_audio_status",
    "wearing_status",
    "safe_listening",
    "safe_volume",
)


@contextmanager
def _open_device(
    mac: str,
    channel: int | None,
    *,
    features=FEATURES,
    find_channel=default_find_channel,
    connect_fn=default_connect,
) -> Iterator[SonyXm6Device]:
    resolved_channel = channel
    if resolved_channel is None:
        resolved_channel = find_channel(mac, DEFAULT_SERVICE_UUID)
    connection = connect_fn(mac, resolved_channel)
    try:
        yield SonyXm6Device(ProtocolSession(connection), features=features)
    finally:
        connection.close()


def format_results(results: dict[str, FeatureResult], *, as_json: bool) -> str:
    if as_json:
        return json.dumps(
            {key: result.to_dict() for key, result in results.items()},
            ensure_ascii=False,
            sort_keys=True,
        )
    lines = []
    for result in results.values():
        if not result.supported:
            value = f"미확인 [{result.error}]"
        else:
            value = _format_human(result.key, result.value)
        lines.append(f"{result.label} ({result.key}): {value}")
    return "\n".join(lines)


def _format_human(key: str, value: Any) -> str:
    if key == "dsee" and isinstance(value, bool):
        return "자동" if value else "꺼짐"
    if isinstance(value, bool):
        return "켜짐" if value else "꺼짐"
    translations = {
        "sound_quality": "음질 우선",
        "stable_connection": "연결 안정성 우선",
        "not_worn": "착용하지 않음",
        "worn": "착용 중",
        "disabled": "사용 안 함",
    }
    if isinstance(value, str):
        return translations.get(value, value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def parse_value(text: str) -> Any:
    lowered = text.lower()
    if lowered in {"on", "true", "yes"}:
        return True
    if lowered in {"off", "false", "no"}:
        return False
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def run_status(mac: str, channel: int | None, *, as_json: bool) -> str:
    with _open_device(mac, channel) as device:
        return format_results(device.get_many(STATUS_KEYS), as_json=as_json)


def run_settings(mac: str, channel: int | None, *, as_json: bool) -> str:
    with _open_device(mac, channel) as device:
        return format_results(device.snapshot(), as_json=as_json)


def run_get(mac: str, channel: int | None, key: str, *, as_json: bool) -> str:
    with _open_device(mac, channel) as device:
        return format_results({key: device.get(key)}, as_json=as_json)


def run_set(
    mac: str,
    channel: int | None,
    key: str,
    value: str,
    *,
    as_json: bool,
) -> str:
    with _open_device(mac, channel) as device:
        return format_results(
            {key: device.set(key, parse_value(value))},
            as_json=as_json,
        )


def run_discover(mac: str, channel: int | None, *, as_json: bool) -> str:
    features = {**FEATURES, **DISCOVERY_FEATURES}
    with _open_device(mac, channel, features=features) as device:
        results = device.get_many(features)
        return format_results(results, as_json=as_json)
