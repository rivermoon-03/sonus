import json
from pathlib import Path

import pytest

from sonus.protocol.framing import (
    DATA_TYPE_ACK,
    DATA_TYPE_MDR,
    Frame,
    FrameChecksumError,
    FrameFormatError,
    decode_frame,
    encode_frame,
)

CAPTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "captures"
    / "2026-08-15-xm6-protocol-info.jsonl"
)


def _captures() -> list[dict[str, str]]:
    return [json.loads(line) for line in CAPTURE.read_text().splitlines()]


def test_encode_matches_observed_protocol_info_request():
    assert encode_frame(DATA_TYPE_MDR, 0, b"\x00\x00") == bytes.fromhex(
        "3e0c000000000200000e3c"
    )


def test_decode_matches_observed_ack_and_response():
    records = _captures()
    ack = decode_frame(bytes.fromhex(records[1]["hex"]))
    response = decode_frame(bytes.fromhex(records[2]["hex"]))

    assert ack == Frame(data_type=DATA_TYPE_ACK, seq=1, payload=b"")
    assert response == Frame(
        data_type=DATA_TYPE_MDR,
        seq=1,
        payload=bytes.fromhex("0100030030320000"),
    )


def test_round_trip_escapes_all_special_bytes():
    payload = bytes([0x3C, 0x3D, 0x3E])
    encoded = encode_frame(DATA_TYPE_MDR, 0, payload)

    assert b"\x3d\x2c" in encoded
    assert b"\x3d\x2d" in encoded
    assert b"\x3d\x2e" in encoded
    assert decode_frame(encoded).payload == payload


@pytest.mark.parametrize("data_type, seq", [(-1, 0), (256, 0), (0, -1), (0, 256)])
def test_encode_rejects_byte_fields_out_of_range(data_type, seq):
    with pytest.raises(FrameFormatError):
        encode_frame(data_type, seq)


def test_decode_rejects_truncated_escape():
    with pytest.raises(FrameFormatError, match="escape"):
        decode_frame(b"\x3e\x0c\x00\x00\x00\x00\x00\x3d\x3c")


@pytest.mark.parametrize(
    "raw",
    [
        bytes.fromhex("3e0c00000000013e4b3c"),
        bytes.fromhex("3e0c00000000013c493c"),
    ],
    ids=["START", "END"],
)
def test_decode_rejects_unescaped_boundary_marker_in_body(raw):
    with pytest.raises(FrameFormatError, match="unescaped"):
        decode_frame(raw)


def test_decode_rejects_declared_length_mismatch_and_trailing_bytes():
    valid = bytearray(encode_frame(DATA_TYPE_MDR, 0, b"\x00"))
    valid[-1:-1] = b"\x00"
    with pytest.raises(FrameFormatError, match="length"):
        decode_frame(bytes(valid))


def test_decode_rejects_bad_checksum():
    raw = bytearray(encode_frame(DATA_TYPE_MDR, 0, b"\x00"))
    raw[-2] ^= 0x01
    with pytest.raises(FrameChecksumError):
        decode_frame(bytes(raw))
