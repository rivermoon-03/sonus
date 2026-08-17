from __future__ import annotations

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


def decode_speak_to_chat(payload: bytes) -> bool:
    return decode_sony_on_off(payload, 0xF7, 0x0C)


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


def decode_connection_mode(payload: bytes) -> str:
    value = decode_byte(payload, 0xE7, 0x00)
    return {0: "sound_quality", 1: "stable_connection"}.get(
        value, f"unknown_{value:02x}"
    )


def decode_auto_power_off(payload: bytes) -> str:
    value = decode_byte(payload, 0x27, 0x05)
    return {
        0x00: "5_minutes",
        0x01: "30_minutes",
        0x02: "60_minutes",
        0x03: "180_minutes",
        0x04: "15_minutes",
        0x10: "when_removed",
        0x11: "disabled",
    }.get(value, f"unknown_{value:02x}")


def decode_voice_guidance(payload: bytes) -> dict[str, Any]:
    body = _body(payload, 0x47, 0x01, minimum=4)
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


def decode_noise_control(payload: bytes) -> dict[str, Any]:
    body = _body(payload, 0x67, 0x19, minimum=9)
    if len(body) != 7:
        raise DecodeError("invalid noise-control response")
    mode_names = {0: "noise_cancelling", 1: "ambient_sound"}
    return {
        "enabled": bool(body[1]),
        "mode": mode_names.get(body[2], f"unknown_{body[2]:02x}"),
        "focus_voice": bool(body[3]),
        "ambient_level": body[4],
        "noise_cancelling": bool(body[5]),
        "adaptive_sensitivity": body[6],
    }


def decode_equalizer(payload: bytes) -> dict[str, Any]:
    body = _body(payload, 0x57, 0x04, minimum=4)
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
