"""Frame codec for the Sony proprietary RFCOMM protocol.

HYPOTHESIS, carried over from community XM4/XM5 reverse-engineering
research (not confirmed for the WH-1000XM6). Verify against the real
device before relying on this for anything beyond probing — see
docs/protocol/README.md.
"""
from __future__ import annotations

from dataclasses import dataclass

START = 0x3E
END = 0x3C
ESCAPE = 0x3D
_ESCAPE_XOR = 0x20
_SPECIAL_BYTES = (START, END, ESCAPE)


class FrameFormatError(Exception):
    """Raised when raw bytes don't form a well-shaped frame."""


class FrameChecksumError(Exception):
    """Raised when a decoded frame's checksum doesn't match its content."""


@dataclass(frozen=True)
class Frame:
    seq: int
    msg_type: int
    payload: bytes


def _checksum(data: bytes) -> int:
    return (0x100 - (sum(data) % 0x100)) % 0x100


def _stuff(data: bytes) -> bytes:
    out = bytearray()
    for byte in data:
        if byte in _SPECIAL_BYTES:
            out.append(ESCAPE)
            out.append(byte ^ _ESCAPE_XOR)
        else:
            out.append(byte)
    return bytes(out)


def _unstuff(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        if byte == ESCAPE:
            if i + 1 >= len(data):
                raise FrameFormatError("truncated escape sequence")
            out.append(data[i + 1] ^ _ESCAPE_XOR)
            i += 2
        else:
            out.append(byte)
            i += 1
    return bytes(out)


def encode_frame(seq: int, msg_type: int, payload: bytes) -> bytes:
    body = bytes([seq, msg_type, len(payload)]) + payload
    body += bytes([_checksum(body)])
    return bytes([START]) + _stuff(body) + bytes([END])


def decode_frame(raw: bytes) -> Frame:
    if len(raw) < 2 or raw[0] != START or raw[-1] != END:
        raise FrameFormatError("frame missing START/END markers")

    body = _unstuff(raw[1:-1])
    if len(body) < 4:
        raise FrameFormatError("frame body too short")

    seq, msg_type, length = body[0], body[1], body[2]
    payload = body[3 : 3 + length]
    if len(payload) != length:
        raise FrameFormatError("payload shorter than declared length")

    received_checksum = body[3 + length]
    expected_checksum = _checksum(body[: 3 + length])
    if received_checksum != expected_checksum:
        raise FrameChecksumError(
            f"checksum mismatch: expected {expected_checksum:#x}, got {received_checksum:#x}"
        )

    return Frame(seq=seq, msg_type=msg_type, payload=payload)
