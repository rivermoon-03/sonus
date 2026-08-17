from __future__ import annotations

import json

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from sonus.device.connection import open_xm6_device
from sonus.device.xm6 import FeatureResult
from sonus.gui.state import (
    GUI_FEATURE_KEYS,
    feature_error_code,
    friendly_error,
    serialize_result,
)
from sonus.messages.registry import FEATURES


class DeviceReadWorker(QObject):
    connecting = pyqtSignal()
    connected = pyqtSignal()
    featureReady = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        mac: str,
        channel: int | None,
        *,
        keys=GUI_FEATURE_KEYS,
        opener=open_xm6_device,
    ) -> None:
        super().__init__()
        self._mac = mac
        self._channel = channel
        self._keys = tuple(keys)
        self._opener = opener

    @pyqtSlot()
    def run(self) -> None:
        self.connecting.emit()
        try:
            with self._opener(self._mac, self._channel) as device:
                self.connected.emit()
                for key in self._keys:
                    try:
                        result = device.get(key)
                    except Exception as error:
                        feature = FEATURES.get(key)
                        result = FeatureResult(
                            key,
                            feature.label if feature else key,
                            supported=False,
                            error=feature_error_code(error),
                        )
                    self.featureReady.emit(
                        json.dumps(serialize_result(result), ensure_ascii=False)
                    )
        except Exception as error:
            self.failed.emit(friendly_error(error))
        finally:
            self.finished.emit()


class DeviceWriteWorker(QObject):
    """Apply one verified setting change without blocking the Qt UI thread."""

    featureReady = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        mac: str,
        channel: int | None,
        key: str,
        value,
        *,
        opener=open_xm6_device,
    ) -> None:
        super().__init__()
        self._mac = mac
        self._channel = channel
        self._key = key
        self._value = value
        self._opener = opener

    @pyqtSlot()
    def run(self) -> None:
        try:
            with self._opener(self._mac, self._channel) as device:
                result = device.set_verified(self._key, self._value)
                self.featureReady.emit(
                    json.dumps(serialize_result(result), ensure_ascii=False)
                )
        except Exception:
            self.failed.emit("설정을 적용하지 못했습니다. 원래 상태를 확인해 주세요.")
        finally:
            self.finished.emit()
