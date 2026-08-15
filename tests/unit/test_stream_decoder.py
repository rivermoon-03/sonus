import pytest

from sonus.protocol.framing import (
    DATA_TYPE_ACK,
    DATA_TYPE_MDR,
    FrameChecksumError,
    FrameFormatError,
    FrameStreamDecoder,
    encode_frame,
)


def test_feed_reassembles_frame_at_every_split_boundary():
    raw = encode_frame(DATA_TYPE_MDR, 0, b"\x00\x00")

    for split in range(1, len(raw)):
        decoder = FrameStreamDecoder()
        assert decoder.feed(raw[:split]) == []
        frames = decoder.feed(raw[split:])
        assert [frame.payload for frame in frames] == [b"\x00\x00"]


def test_feed_reassembles_escaped_end_split_across_chunks():
    raw = encode_frame(DATA_TYPE_MDR, 0, b"\x3c")
    escape_index = raw.index(b"\x3d\x2c")
    decoder = FrameStreamDecoder()

    assert decoder.feed(raw[: escape_index + 1]) == []
    frames = decoder.feed(raw[escape_index + 1 :])

    assert [frame.payload for frame in frames] == [b"\x3c"]


def test_feed_returns_multiple_frames_from_one_chunk():
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, bytes.fromhex("0100030030320000"))
    frames = FrameStreamDecoder().feed(ack + response)

    assert [frame.data_type for frame in frames] == [DATA_TYPE_ACK, DATA_TYPE_MDR]


def test_feed_discards_noise_before_start_marker():
    raw = encode_frame(DATA_TYPE_ACK, 1)

    assert FrameStreamDecoder().feed(b"noise" + raw)[0].data_type == DATA_TYPE_ACK


def test_invalid_frame_is_consumed_and_next_frame_can_be_recovered():
    invalid = bytearray(encode_frame(DATA_TYPE_MDR, 0, b"\x00"))
    invalid[-2] ^= 0x01
    valid = encode_frame(DATA_TYPE_ACK, 1)
    decoder = FrameStreamDecoder()

    with pytest.raises(FrameChecksumError):
        decoder.feed(bytes(invalid) + valid)

    assert decoder.feed(b"")[0].data_type == DATA_TYPE_ACK


def test_invalid_escape_before_end_does_not_consume_next_frame():
    invalid = bytes.fromhex("3e0c00000000003d3c")
    valid = encode_frame(DATA_TYPE_ACK, 1)
    decoder = FrameStreamDecoder()

    with pytest.raises(FrameFormatError):
        decoder.feed(invalid + valid)

    assert decoder.feed(b"")[0].data_type == DATA_TYPE_ACK


def test_bare_start_resynchronizes_to_a_following_frame():
    malformed = b"\x3e\x00\x00\x00"
    valid = encode_frame(DATA_TYPE_ACK, 1)
    decoder = FrameStreamDecoder()

    with pytest.raises(FrameFormatError):
        decoder.feed(malformed + valid)

    assert decoder.feed(b"")[0].data_type == DATA_TYPE_ACK


def test_start_after_invalid_escape_resynchronizes_to_a_following_frame():
    malformed = b"\x3e\x00\x00\x00\x3d"
    valid = encode_frame(DATA_TYPE_ACK, 1)
    decoder = FrameStreamDecoder()

    with pytest.raises(FrameFormatError):
        decoder.feed(malformed + valid)

    assert decoder.feed(b"")[0].data_type == DATA_TYPE_ACK


def test_frames_decoded_before_an_error_are_returned_after_recovery():
    valid = encode_frame(DATA_TYPE_ACK, 1)
    invalid = bytearray(encode_frame(DATA_TYPE_MDR, 0, b"\x00"))
    invalid[-2] ^= 0x01
    decoder = FrameStreamDecoder()

    with pytest.raises(FrameChecksumError):
        decoder.feed(valid + bytes(invalid))

    assert [frame.data_type for frame in decoder.feed(b"")] == [DATA_TYPE_ACK]


def test_incomplete_frame_over_limit_resets_buffer():
    decoder = FrameStreamDecoder(max_frame_size=12)

    with pytest.raises(FrameFormatError, match="maximum"):
        decoder.feed(b"\x3e" + b"\x00" * 12)

    assert decoder.feed(encode_frame(DATA_TYPE_ACK, 1))[0].data_type == DATA_TYPE_ACK


def test_reset_discards_an_incomplete_frame():
    raw = encode_frame(DATA_TYPE_ACK, 1)
    decoder = FrameStreamDecoder()

    assert decoder.feed(raw[:-1]) == []
    decoder.reset()

    assert decoder.feed(raw[-1:]) == []


def test_reset_discards_frames_queued_before_an_error():
    valid = encode_frame(DATA_TYPE_ACK, 1)
    invalid = bytearray(encode_frame(DATA_TYPE_MDR, 0, b"\x00"))
    invalid[-2] ^= 0x01
    decoder = FrameStreamDecoder()

    with pytest.raises(FrameChecksumError):
        decoder.feed(valid + bytes(invalid))
    decoder.reset()

    assert decoder.feed(b"") == []
