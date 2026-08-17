from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class DecodeError(ValueError):
    """응답 payload가 등록된 명령 형식과 다를 때 발생한다."""


def _body(payload: bytes, command: int, item_type: int, minimum: int = 3) -> bytes:
    expected = bytes((command, item_type))
    if len(payload) < minimum or payload[:2] != expected:
        actual = payload[:2].hex() if len(payload) >= 2 else payload.hex()
        raise DecodeError(f"expected {expected.hex()}, got {actual}")
    return payload[2:]


def decode_string(payload: bytes, command: int, item_type: int) -> str:
    body = _body(payload, command, item_type)
    length = body[0]
    value = body[1:]
    if len(value) != length:
        raise DecodeError(f"string length is {length}, got {len(value)} bytes")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DecodeError("device string is not UTF-8") from error


def decode_battery(payload: bytes, command: int, item_type: int) -> dict[str, Any]:
    body = _body(payload, command, item_type, minimum=4)
    if len(body) != 2 or body[0] > 100 or body[1] not in (0, 1):
        raise DecodeError("invalid battery response")
    return {"level": body[0], "charging": bool(body[1])}


def decode_bool(payload: bytes, command: int, item_type: int) -> bool:
    body = _body(payload, command, item_type)
    if len(body) < 1 or body[0] not in (0, 1):
        raise DecodeError("invalid boolean response")
    return bool(body[0])


def decode_byte(payload: bytes, command: int, item_type: int) -> int:
    body = _body(payload, command, item_type)
    return body[0]


def decode_bytes(payload: bytes, command: int, item_type: int) -> list[int]:
    return list(_body(payload, command, item_type))


def decode_signed_byte(payload: bytes, command: int, item_type: int) -> int:
    body = _body(payload, command, item_type)
    return int.from_bytes(body[:1], "big", signed=True)


def decode_wearing_status(payload: bytes) -> str:
    code = decode_byte(payload, 0xF3, 0x00)
    return {
        0x00: "worn",
        0x01: "invalid",
        0x02: "left_not_worn",
        0x03: "right_not_worn",
        0x04: "not_worn",
    }.get(code, f"unknown_{code:02x}")


def decode_sony_on_off(payload: bytes, command: int, item_type: int) -> bool:
    value = decode_byte(payload, command, item_type)
    if value not in (0, 1):
        raise DecodeError("invalid Sony on/off value")
    return value == 0


def decode_speak_to_chat(payload: bytes, command: int = 0xF7) -> dict[str, bool]:
    body = _body(payload, command, 0x0C, minimum=4)
    if len(body) != 2 or any(value not in (0, 1) for value in body):
        raise DecodeError("invalid Speak-to-Chat response")
    return {"enabled": body[0] == 0, "preview": body[1] == 0}


def decode_codec(payload: bytes) -> str:
    value = decode_byte(payload, 0x13, 0x02)
    return {
        0x00: "unsettled",
        0x01: "SBC",
        0x02: "AAC",
        0x10: "LDAC",
        0x20: "aptX",
        0x21: "aptX HD",
        0x30: "LC3",
        0xFF: "other",
    }.get(value, f"unknown_{value:02x}")


def decode_connection_mode(payload: bytes, command: int = 0xE7) -> str:
    value = decode_byte(payload, command, 0x00)
    return {0: "sound_quality", 1: "stable_connection"}.get(
        value, f"unknown_{value:02x}"
    )


_AUTO_POWER_OFF_VALUES = {
        0x00: "5_minutes",
        0x01: "30_minutes",
        0x02: "60_minutes",
        0x03: "180_minutes",
        0x04: "15_minutes",
        0x10: "when_removed",
        0x11: "disabled",
}


def decode_auto_power_off(payload: bytes, command: int = 0x27) -> dict[str, str]:
    body = _body(payload, command, 0x05, minimum=4)
    if len(body) != 2:
        raise DecodeError("invalid auto-power-off response")
    return {
        "mode": _AUTO_POWER_OFF_VALUES.get(body[0], f"unknown_{body[0]:02x}"),
        "last_mode": _AUTO_POWER_OFF_VALUES.get(body[1], f"unknown_{body[1]:02x}"),
    }


def decode_voice_guidance(payload: bytes, command: int = 0x47) -> dict[str, Any]:
    body = _body(payload, command, 0x01, minimum=4)
    if len(body) != 2:
        raise DecodeError("invalid voice-guidance response")
    languages = {
        0x01: "english",
        0x0B: "japanese",
        0x0F: "korean",
        0xF0: "chinese",
    }
    if body[0] not in (0, 1):
        raise DecodeError("invalid voice-guidance on/off value")
    return {
        "enabled": body[0] == 0,
        "language": languages.get(body[1], f"code_{body[1]:02x}"),
    }


def decode_protocol(payload: bytes) -> dict[str, Any]:
    body = _body(payload, 0x01, 0x00, minimum=8)
    if len(body) != 6:
        raise DecodeError("invalid protocol-info response")
    version_bytes = body[:4]
    display_version = version_bytes[-2:].decode("ascii", errors="replace")
    return {
        "version": display_version,
        "version_raw": version_bytes.hex(),
        # EnableDisable은 일반 boolean과 반대로 0이 ENABLE이다.
        "table1": body[4] == 0,
        "table2": body[5] == 0,
    }


def decode_noise_control(payload: bytes, command: int = 0x67) -> dict[str, Any]:
    body = _body(payload, command, 0x19, minimum=9)
    if len(body) != 7:
        raise DecodeError("invalid noise-control response")
    mode_names = {0: "noise_cancelling", 1: "ambient_sound"}
    return {
        "enabled": body[1] == 1,
        "mode": mode_names.get(body[2], f"unknown_{body[2]:02x}"),
        "focus_voice": body[3] == 1,
        "ambient_level": body[4],
        "auto_ambient": body[5] == 1,
        "adaptive_sensitivity": body[6],
    }


def decode_equalizer(
    payload: bytes, command: int = 0x57, item_type: int = 0x04
) -> dict[str, Any]:
    body = _body(payload, command, item_type, minimum=4)
    preset = body[0]
    band_count = body[1]
    bands = list(body[2:])
    if len(bands) != band_count:
        raise DecodeError(f"equalizer declares {band_count} bands, got {len(bands)}")
    return {"preset": preset, "bands": bands}


def encode_dsee(value: Any) -> bytes:
    if isinstance(value, str):
        normalized = value.lower()
        if normalized == "auto":
            value = True
        elif normalized == "off":
            value = False
    if not isinstance(value, bool):
        raise ValueError("DSEE value must be on/auto or off")
    return b"\xE8\x01" + bytes((int(value),))


def _mapping(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be an object")
    missing = fields - value.keys()
    if missing:
        raise ValueError(f"{label} is missing: {', '.join(sorted(missing))}")
    return value


def _sony_enabled(value: Any, label: str) -> int:
    if not isinstance(value, bool):
        raise TypeError(f"{label} must be boolean")
    return 0 if value else 1


def encode_noise_control(value: Any) -> bytes:
    value = _mapping(
        value,
        {
            "enabled",
            "mode",
            "focus_voice",
            "ambient_level",
            "auto_ambient",
            "adaptive_sensitivity",
        },
        "noise control",
    )
    mode = {"noise_cancelling": 0, "ambient_sound": 1}.get(value["mode"])
    if mode is None:
        raise ValueError("noise-control mode must be noise_cancelling or ambient_sound")
    level = value["ambient_level"]
    sensitivity = value["adaptive_sensitivity"]
    if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 20:
        raise ValueError("ambient level must be between 1 and 20")
    if not isinstance(sensitivity, int) or isinstance(sensitivity, bool) or sensitivity not in range(3):
        raise ValueError("adaptive sensitivity must be 0, 1, or 2")
    return bytes(
        (
            0x68,
            0x19,
            0x01,
            0x01 if value["enabled"] else 0x00,
            mode,
            0x01 if value["focus_voice"] else 0x00,
            level,
            0x01 if value["auto_ambient"] else 0x00,
            sensitivity,
        )
    )


def encode_equalizer(value: Any) -> bytes:
    value = _mapping(value, {"preset", "bands"}, "equalizer")
    preset = value["preset"]
    bands = value["bands"]
    if not isinstance(preset, int) or isinstance(preset, bool) or not 0 <= preset <= 0xFF:
        raise ValueError("equalizer preset must be one byte")
    if not isinstance(bands, (list, tuple)) or len(bands) != 10:
        raise ValueError("equalizer must contain 10 bands")
    if any(not isinstance(item, int) or isinstance(item, bool) or not 0 <= item <= 20 for item in bands):
        raise ValueError("equalizer bands must be between 0 and 20")
    return bytes((0x58, 0x00, preset, len(bands), *bands))


def encode_connection_mode(value: Any) -> bytes:
    try:
        encoded = {"sound_quality": 0, "stable_connection": 1}[value]
    except (KeyError, TypeError) as error:
        raise ValueError("connection mode must be sound_quality or stable_connection") from error
    return bytes((0xE8, 0x00, encoded))


def encode_system_toggle(type_id: int, value: Any) -> bytes:
    if not isinstance(type_id, int) or isinstance(type_id, bool) or not 0 <= type_id <= 0xFF:
        raise ValueError("system setting type must be one byte")
    return bytes((0xF8, type_id, _sony_enabled(value, "system setting")))


def encode_speak_to_chat(value: Any) -> bytes:
    value = _mapping(value, {"enabled", "preview"}, "Speak-to-Chat")
    return bytes(
        (
            0xF8,
            0x0C,
            _sony_enabled(value["enabled"], "Speak-to-Chat enabled"),
            _sony_enabled(value["preview"], "Speak-to-Chat preview"),
        )
    )


def encode_auto_power_off(value: Any) -> bytes:
    value = _mapping(value, {"mode", "last_mode"}, "auto power off")
    reverse = {name: code for code, name in _AUTO_POWER_OFF_VALUES.items()}
    try:
        current = reverse[value["mode"]]
        last = reverse[value["last_mode"]]
    except (KeyError, TypeError) as error:
        raise ValueError("invalid auto-power-off mode") from error
    return bytes((0x28, 0x05, current, last))


_VOICE_GUIDANCE_LANGUAGES = {
    "english": 0x01,
    "japanese": 0x0B,
    "korean": 0x0F,
    "chinese": 0xF0,
}


def encode_voice_guidance(value: Any) -> bytes:
    value = _mapping(value, {"enabled", "language"}, "voice guidance")
    try:
        language = _VOICE_GUIDANCE_LANGUAGES[value["language"]]
    except (KeyError, TypeError) as error:
        raise ValueError("unsupported voice-guidance language") from error
    return bytes((0x48, 0x01, _sony_enabled(value["enabled"], "voice guidance"), language))


def encode_voice_guidance_volume(value: Any) -> bytes:
    if not isinstance(value, int) or isinstance(value, bool) or not -2 <= value <= 2:
        raise ValueError("voice-guidance volume must be between -2 and 2")
    return b"\x48\x20" + value.to_bytes(1, "big", signed=True) + b"\x01"


def encode_safe_listening(value: Any) -> bytes:
    value = _mapping(value, {"enabled", "preview"}, "safe listening")
    return bytes(
        (
            0x58,
            0x02,
            _sony_enabled(value["enabled"], "safe listening"),
            _sony_enabled(value["preview"], "safe-listening preview"),
        )
    )


def encode_safe_volume(value: Any) -> bytes:
    value = _mapping(value, {"limited", "enabled"}, "safe volume")
    return bytes(
        (
            0x58,
            0x04,
            _sony_enabled(value["limited"], "volume limitation"),
            _sony_enabled(value["enabled"], "safe-volume control"),
        )
    )
