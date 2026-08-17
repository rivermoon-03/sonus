"""Bluetooth device discovery helpers for the desktop application."""

from __future__ import annotations

import re


_DEVICE = re.compile(
    r"^Device\s+(?P<mac>[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s+(?P<name>.+)$"
)


def parse_bluetoothctl_devices(output: str) -> list[dict[str, object]]:
    """Parse ``bluetoothctl devices`` while preserving display order."""
    devices: list[dict[str, object]] = []
    seen: set[str] = set()
    for line in output.splitlines():
        match = _DEVICE.fullmatch(line.strip())
        if match is None:
            continue
        mac = match.group("mac").upper()
        if mac in seen:
            continue
        seen.add(mac)
        devices.append({"mac": mac, "name": match.group("name").strip(), "channel": 9})
    return devices
