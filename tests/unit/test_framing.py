import pytest

from sonus.protocol.framing import (
    Frame,
    FrameChecksumError,
    FrameFormatError,
    decode_frame,
    encode_frame,
)


def test_encode_decode_round_trip_no_escaping_needed():
    encoded = encode_frame(seq=1, msg_type=0x0C, payload=b"\x01\x02\x03")
    decoded = decode_frame(encoded)
    assert decoded == Frame(seq=1, msg_type=0x0C, payload=b"\x01\x02\x03")


def test_encode_starts_and_ends_with_markers():
    encoded = encode_frame(seq=0, msg_type=0x00, payload=b"")
    assert encoded[0] == 0x3E
    assert encoded[-1] == 0x3C


def test_encode_escapes_special_bytes_in_payload():
    # payload contains START, END, and ESCAPE bytes that must be stuffed
    encoded = encode_frame(seq=0, msg_type=0x01, payload=b"\x3e\x3c\x3d")
    # None of the special bytes should appear "bare" between the outer markers
    inner = encoded[1:-1]
    i = 0
    while i < len(inner):
        if inner[i] == 0x3D:
            i += 2  # escaped byte, skip both
            continue
        assert inner[i] not in (0x3E, 0x3C, 0x3D)
        i += 1


def test_decode_round_trips_escaped_payload():
    payload = b"\x3e\x3c\x3d\x00\xff"
    encoded = encode_frame(seq=5, msg_type=0x02, payload=payload)
    decoded = decode_frame(encoded)
    assert decoded == Frame(seq=5, msg_type=0x02, payload=payload)


def test_decode_raises_on_bad_checksum():
    encoded = bytearray(encode_frame(seq=1, msg_type=0x0C, payload=b"\x01"))
    encoded[-2] ^= 0xFF  # corrupt the checksum byte
    with pytest.raises(FrameChecksumError):
        decode_frame(bytes(encoded))


def test_decode_raises_on_missing_markers():
    with pytest.raises(FrameFormatError):
        decode_frame(b"\x01\x02\x03")
