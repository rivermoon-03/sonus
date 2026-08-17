"""Persistent preferences for the desktop application."""

from __future__ import annotations

import json

from PyQt6.QtCore import QSettings


class GuiSettings:
    """Typed facade over ``QSettings`` with conservative defaults."""

    def __init__(self, backend: QSettings | None = None) -> None:
        self._backend = backend or QSettings("Sonus", "Sonus")

    @property
    def theme(self) -> str:
        value = str(self._backend.value("appearance/theme", "light"))
        return value if value in {"light", "dark"} else "light"

    @theme.setter
    def theme(self, value: str) -> None:
        self._backend.setValue(
            "appearance/theme", value if value in {"light", "dark"} else "light"
        )

    @property
    def device_mac(self) -> str:
        return str(self._backend.value("device/mac", "")).strip().upper()

    @device_mac.setter
    def device_mac(self, value: str) -> None:
        self._backend.setValue("device/mac", value.strip().upper())

    @property
    def channel(self) -> int | None:
        value = self._backend.value("device/channel")
        if value in (None, ""):
            return None
        try:
            channel = int(value)
        except (TypeError, ValueError):
            return None
        return channel if 1 <= channel <= 30 else None

    @channel.setter
    def channel(self, value: int | None) -> None:
        if value is None:
            self._backend.remove("device/channel")
        else:
            self._backend.setValue("device/channel", int(value))

    @property
    def window_geometry(self) -> bytes | None:
        value = self._backend.value("window/geometry")
        return bytes(value) if value is not None else None

    @window_geometry.setter
    def window_geometry(self, value: bytes) -> None:
        self._backend.setValue("window/geometry", value)

    @property
    def disclaimer_accepted(self) -> bool:
        return self._backend.value("legal/disclaimer_accepted", False, type=bool)

    @disclaimer_accepted.setter
    def disclaimer_accepted(self, value: bool) -> None:
        self._backend.setValue("legal/disclaimer_accepted", bool(value))
        self._backend.sync()

    @property
    def saved_devices(self) -> list[dict[str, object]]:
        raw = self._backend.value("device/saved", "[]")
        try:
            values = json.loads(str(raw))
        except (TypeError, ValueError):
            return []
        if not isinstance(values, list):
            return []
        result = []
        for value in values:
            if not isinstance(value, dict):
                continue
            mac = str(value.get("mac", "")).strip().upper()
            name = str(value.get("name", "")).strip()
            try:
                channel = int(value.get("channel", 9))
            except (TypeError, ValueError):
                continue
            if mac and name and 1 <= channel <= 30:
                result.append({"mac": mac, "channel": channel, "name": name})
        return result

    def remember_device(self, mac: str, channel: int, name: str) -> None:
        normalized = mac.strip().upper()
        entry = {"mac": normalized, "channel": int(channel), "name": name.strip()}
        remaining = [item for item in self.saved_devices if item["mac"] != normalized]
        self._backend.setValue(
            "device/saved", json.dumps([entry, *remaining], ensure_ascii=False)
        )
        self.device_mac = normalized
        self.channel = channel
        self._backend.sync()
