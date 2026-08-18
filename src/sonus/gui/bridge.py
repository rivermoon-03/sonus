"""Narrow WebChannel API exposed to the bundled interface."""

from __future__ import annotations

import json
import re

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from sonus.gui.settings import GuiSettings
from sonus.messages.registry import FEATURES


_MAC_PATTERN = re.compile(r"^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$")


class GuiBridge(QObject):
    """Narrow, deliberately write-free interface between JavaScript and Python."""

    initialState = pyqtSignal(str)
    connectionState = pyqtSignal(str)
    featureState = pyqtSignal(str)
    devicesState = pyqtSignal(str)
    refreshFinished = pyqtSignal()
    userMessage = pyqtSignal(str)
    connectRequested = pyqtSignal(str, int)
    devicesRequested = pyqtSignal()
    debugRequested = pyqtSignal()
    quickRequested = pyqtSignal()
    featureWriteRequested = pyqtSignal(str, str)
    quitRequested = pyqtSignal()

    def __init__(self, settings: GuiSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings

    @pyqtSlot()
    def requestInitialState(self) -> None:
        self.initialState.emit(
            json.dumps(
                {
                    "theme": self.settings.theme,
                    "mac": self.settings.device_mac,
                    "channel": self.settings.channel,
                    "readOnly": False,
                    "disclaimerAccepted": self.settings.disclaimer_accepted,
                    "savedDevices": self.settings.saved_devices,
                },
                ensure_ascii=False,
            )
        )

    @pyqtSlot(str, int)
    def connectDevice(self, mac: str, channel: int) -> None:
        normalized = mac.strip().upper()
        if not _MAC_PATTERN.fullmatch(normalized):
            self.userMessage.emit("Bluetooth 주소를 확인해 주세요.")
            return
        if not 1 <= channel <= 30:
            self.userMessage.emit("RFCOMM 채널은 1부터 30 사이여야 합니다.")
            return
        self.settings.device_mac = normalized
        self.settings.channel = channel
        self.connectRequested.emit(normalized, channel)

    @pyqtSlot(str, int, str)
    def connectNamedDevice(self, mac: str, channel: int, name: str) -> None:
        normalized = mac.strip().upper()
        if not _MAC_PATTERN.fullmatch(normalized):
            self.userMessage.emit("Bluetooth 주소를 확인해 주세요.")
            return
        if not 1 <= channel <= 30:
            self.userMessage.emit("RFCOMM 채널은 1부터 30 사이여야 합니다.")
            return
        self.settings.remember_device(normalized, channel, name or "WH-1000XM6")
        self.connectRequested.emit(normalized, channel)

    @pyqtSlot()
    def requestDevices(self) -> None:
        self.devicesRequested.emit()

    @pyqtSlot()
    def requestDebugState(self) -> None:
        self.debugRequested.emit()

    @pyqtSlot()
    def requestQuickState(self) -> None:
        self.quickRequested.emit()

    @pyqtSlot()
    def acceptDisclaimer(self) -> None:
        self.settings.disclaimer_accepted = True

    @pyqtSlot()
    def rejectDisclaimer(self) -> None:
        self.quitRequested.emit()

    @pyqtSlot(str, str)
    def setFeature(self, key: str, encoded_value: str) -> None:
        if not self.settings.disclaimer_accepted:
            self.userMessage.emit("설정 변경 안내에 먼저 동의해 주세요.")
            return
        feature = FEATURES.get(key)
        if feature is None or not feature.writable:
            self.userMessage.emit("이 설정은 안전한 쓰기가 검증되지 않았습니다.")
            return
        try:
            value = json.loads(encoded_value)
        except (TypeError, ValueError):
            self.userMessage.emit("설정값을 확인해 주세요.")
            return
        self.featureWriteRequested.emit(key, json.dumps(value, ensure_ascii=False))

    @pyqtSlot()
    def refresh(self) -> None:
        mac = self.settings.device_mac
        channel = self.settings.channel
        if not mac or channel is None:
            self.userMessage.emit("먼저 헤드셋을 연결해 주세요.")
            return
        self.connectRequested.emit(mac, channel)

    @pyqtSlot(str)
    def saveTheme(self, theme: str) -> None:
        self.settings.theme = theme

    def emit_connection(self, state: str, message: str = "") -> None:
        self.connectionState.emit(
            json.dumps({"state": state, "message": message}, ensure_ascii=False)
        )
