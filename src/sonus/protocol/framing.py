"""Pure frame codec for the Sony MDR protocol observed on WH-1000XM6."""
from __future__ import annotations

from dataclasses import dataclass

START = 0x3E
END = 0x3C
ESCAPE = 0x3D
DATA_TYPE_ACK = 0x01
DATA_TYPE_MDR = 0x0C
DATA_TYPE_MDR_NO2 = 0x0E
_SPECIAL_BYTES = (START, END, ESCAPE)
_ESCAPED_BYTES = {0x2C: END, 0x2D: ESCAPE, 0x2E: START}


class FrameFormatError(Exception):
    """Raised when raw bytes do not form one complete valid frame."""


class FrameChecksumError(Exception):
    """Raised when a decoded frame has an invalid checksum."""


@dataclass(frozen=True)
class Frame:
    data_type: int
    seq: int
    payload: bytes


def _validate_byte(name: str, value: int) -> None:
    if not isinstance(value, int) or not 0 <= value <= 0xFF:
        raise FrameFormatError(f"{name} must be an integer from 0 to 255")


def _checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def _stuff(data: bytes) -> bytes:
    out = bytearray()
    for byte in data:
        if byte in _SPECIAL_BYTES:
            out.extend((ESCAPE, byte - 0x10))
        else:
            out.append(byte)
    return bytes(out)


def _unstuff(data: bytes) -> bytes:
    out = bytearray()
    index = 0
    while index < len(data):
        byte = data[index]
        if byte in (START, END):
            raise FrameFormatError("unescaped frame marker in body")
        if byte != ESCAPE:
            out.append(byte)
            index += 1
            continue
        if index + 1 >= len(data):
            raise FrameFormatError("truncated escape sequence")
        escaped = data[index + 1]
        if escaped not in _ESCAPED_BYTES:
            raise FrameFormatError(f"invalid escaped byte: {escaped:#x}")
        out.append(_ESCAPED_BYTES[escaped])
        index += 2
    return bytes(out)


def encode_frame(
    data_type: int,
    seq: int,
    payload: bytes = b"",
) -> bytes:
    """Encode one observed MDR frame.
    """
    _validate_byte("data_type", data_type)
    _validate_byte("seq", seq)
    if len(payload) > 0xFFFFFFFF:
        raise FrameFormatError("payload is too large for a 4-byte length")
    body = bytes([data_type, seq]) + len(payload).to_bytes(4, "big") + payload
    body += bytes([_checksum(body)])
    return bytes([START]) + _stuff(body) + bytes([END])


def decode_frame(raw: bytes) -> Frame:
    if len(raw) < 2 or raw[0] != START or raw[-1] != END:
        raise FrameFormatError("frame missing START/END markers")
    body = _unstuff(raw[1:-1])
    if len(body) < 7:
        raise FrameFormatError("frame body too short")

    data_type, seq = body[0], body[1]
    length = int.from_bytes(body[2:6], "big")
    expected_size = 6 + length + 1
    if len(body) != expected_size:
        raise FrameFormatError(
            f"frame length mismatch: declared {length}, body has {len(body) - 7} payload bytes"
        )

    received_checksum = body[-1]
    expected_checksum = _checksum(body[:-1])
    if received_checksum != expected_checksum:
        raise FrameChecksumError(
            f"checksum mismatch: expected {expected_checksum:#x}, got {received_checksum:#x}"
        )
    return Frame(data_type=data_type, seq=seq, payload=body[6:-1])


class FrameStreamDecoder:
    """Incrementally reconstruct MDR frames from RFCOMM byte chunks."""

    def __init__(self, max_frame_size: int = 4096) -> None:
        if max_frame_size < 2:
            raise ValueError("max_frame_size must be at least 2")
        self._max_frame_size = max_frame_size
        self._buffer = bytearray()
        self._ready: list[Frame] = []

    def reset(self) -> None:
        self._buffer.clear()
        self._ready.clear()

    def feed(self, data: bytes) -> list[Frame]:
        self._buffer.extend(data)
        frames, self._ready = self._ready, []

        try:
            while True:
                try:
                    start = self._buffer.index(START)
                except ValueError:
                    self._buffer.clear()
                    return frames

                if start:
                    del self._buffer[:start]

                end = self._find_end()
                if end is None:
                    if len(self._buffer) > self._max_frame_size:
                        self._buffer.clear()
                        raise FrameFormatError("packed frame exceeds maximum size")
                    return frames

                if self._buffer[end] == START:
                    del self._buffer[:end]
                    raise FrameFormatError("unescaped frame marker in body")

                raw = bytes(self._buffer[: end + 1])
                del self._buffer[: end + 1]
                if len(raw) > self._max_frame_size:
                    raise FrameFormatError("packed frame exceeds maximum size")
                frames.append(decode_frame(raw))
        except (FrameChecksumError, FrameFormatError):
            self._ready = frames
            raise

    def _find_end(self) -> int | None:
        index = 1
        while index < len(self._buffer):
            byte = self._buffer[index]
            if byte == ESCAPE:
                if index + 1 == len(self._buffer):
                    return None
                escaped = self._buffer[index + 1]
                if escaped in _ESCAPED_BYTES:
                    index += 2
                    continue
                if escaped in (END, START):
                    return index + 1
                index += 2
                continue
            if byte == START:
                return index
            if byte == END:
                return index
            index += 1
        return None
