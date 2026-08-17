from collections import deque

import pytest

from sonus.protocol.framing import (
    DATA_TYPE_ACK,
    DATA_TYPE_MDR,
    decode_frame,
    encode_frame,
)
from sonus.protocol.session import ProtocolSession, ProtocolTimeoutError


class FakeTransport:
    def __init__(self, chunks):
        self.sent = []
        self._chunks = deque(chunks)

    def send(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, bufsize: int, timeout: float) -> bytes:
        if not self._chunks:
            raise TimeoutError("no scripted data")
        chunk = self._chunks.popleft()
        if chunk is None:
            raise TimeoutError("scripted timeout")
        return chunk


def test_request_handles_ack_and_response_in_one_recv():
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01\x00")
    transport = FakeTransport([ack + response])

    result = ProtocolSession(transport).request(DATA_TYPE_MDR, b"\x00\x00")

    assert result.payload == b"\x01\x00"
    assert decode_frame(transport.sent[0]).payload == b"\x00\x00"
    assert decode_frame(transport.sent[1]).data_type == DATA_TYPE_ACK
    assert decode_frame(transport.sent[1]).seq == 0


def test_request_acknowledges_and_queues_data_after_ack_in_same_recv():
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01\x00")
    notification = encode_frame(DATA_TYPE_MDR, 1, b"\xc9\x01")
    transport = FakeTransport([ack + response + notification])
    session = ProtocolSession(transport)

    result = session.request(DATA_TYPE_MDR, b"\x00\x00")

    assert result.payload == b"\x01\x00"
    assert [frame.payload for frame in session.pop_notifications()] == [b"\xc9\x01"]
    sent = [decode_frame(raw) for raw in transport.sent]
    assert [(frame.data_type, frame.seq) for frame in sent] == [
        (DATA_TYPE_MDR, 0),
        (DATA_TYPE_ACK, 0),
        (DATA_TYPE_ACK, 0),
    ]


def test_request_drains_queued_notification_before_next_request():
    ack1 = encode_frame(DATA_TYPE_ACK, 1)
    response1 = encode_frame(DATA_TYPE_MDR, 1, b"\x01\x00")
    notification = encode_frame(DATA_TYPE_MDR, 1, b"\xc9\x01")
    ack2 = encode_frame(DATA_TYPE_ACK, 0)
    response2 = encode_frame(DATA_TYPE_MDR, 0, b"\x03\x00")
    transport = FakeTransport([ack1, response1 + notification, ack2, response2])
    session = ProtocolSession(transport)

    first = session.request(DATA_TYPE_MDR, b"\x00\x00")

    assert first.payload == b"\x01\x00"
    assert [frame.payload for frame in session.pop_notifications()] == [b"\xc9\x01"]
    assert session.request(DATA_TYPE_MDR, b"\x02\x00").payload == b"\x03\x00"


def test_request_reassembles_a_response_split_across_recvs():
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01\x00")
    split = len(response) - 2
    transport = FakeTransport([ack + response[:split], response[split:]])

    result = ProtocolSession(transport).request(DATA_TYPE_MDR, b"\x00\x00")

    assert result.payload == b"\x01\x00"
    assert [(frame.data_type, frame.seq) for frame in map(decode_frame, transport.sent)] == [
        (DATA_TYPE_MDR, 0),
        (DATA_TYPE_ACK, 0),
    ]


def test_request_reassembles_large_split_notification_and_acknowledges_it():
    ack = encode_frame(DATA_TYPE_ACK, 1)
    notification_payload = bytes(range(256)) * 5
    notification = encode_frame(DATA_TYPE_MDR, 1, notification_payload)
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01\x00")
    split_points = (len(notification) // 4, len(notification) // 2)
    notification_chunks = [
        notification[: split_points[0]],
        notification[split_points[0] : split_points[1]],
        notification[split_points[1] :],
    ]
    transport = FakeTransport([ack, *notification_chunks, response])
    session = ProtocolSession(transport)

    result = session.request(
        DATA_TYPE_MDR,
        b"\x00\x00",
        response_matcher=lambda frame: frame.payload.startswith(b"\x01"),
    )

    assert result.payload == b"\x01\x00"
    notifications = session.pop_notifications()
    assert [frame.payload for frame in notifications] == [notification_payload]
    sent = [decode_frame(raw) for raw in transport.sent]
    assert [(frame.data_type, frame.seq) for frame in sent] == [
        (DATA_TYPE_MDR, 0),
        (DATA_TYPE_ACK, 0),
        (DATA_TYPE_ACK, 0),
    ]


def test_request_retains_matching_response_received_before_ack():
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01\x00")
    ack = encode_frame(DATA_TYPE_ACK, 1)
    transport = FakeTransport([response, ack])

    result = ProtocolSession(transport).request(DATA_TYPE_MDR, b"\x00\x00")

    assert result.payload == b"\x01\x00"
    assert [(frame.data_type, frame.seq) for frame in map(decode_frame, transport.sent)] == [
        (DATA_TYPE_MDR, 0),
        (DATA_TYPE_ACK, 0),
    ]


def test_request_queues_notification_before_matching_response():
    notification = encode_frame(DATA_TYPE_MDR, 1, b"\xc9\x01")
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01\x00")
    transport = FakeTransport([notification, ack, response])
    session = ProtocolSession(transport)

    result = session.request(
        DATA_TYPE_MDR,
        b"\x00\x00",
        response_matcher=lambda frame: frame.payload.startswith(b"\x01"),
    )

    assert result.payload == b"\x01\x00"
    assert [frame.payload for frame in session.pop_notifications()] == [b"\xc9\x01"]
    assert session.pop_notifications() == []
    sent = [decode_frame(raw) for raw in transport.sent]
    assert [(frame.data_type, frame.seq) for frame in sent[1:]] == [
        (DATA_TYPE_ACK, 0),
        (DATA_TYPE_ACK, 0),
    ]


def test_request_retries_only_while_waiting_for_ack():
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01")
    transport = FakeTransport([None, ack, response])

    ProtocolSession(transport, retries=1).request(DATA_TYPE_MDR, b"\x00")

    requests = [
        decode_frame(raw)
        for raw in transport.sent
        if decode_frame(raw).data_type != DATA_TYPE_ACK
    ]
    assert len(requests) == 2
    assert requests[0] == requests[1]


def test_request_retries_when_matching_ack_has_a_payload():
    malformed_ack = encode_frame(DATA_TYPE_ACK, 1, b"\x00")
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01")
    transport = FakeTransport([malformed_ack, None, ack, response])

    result = ProtocolSession(transport, retries=1).request(DATA_TYPE_MDR, b"\x00")

    assert result.payload == b"\x01"
    requests = [
        decode_frame(raw)
        for raw in transport.sent
        if decode_frame(raw).data_type != DATA_TYPE_ACK
    ]
    assert len(requests) == 2


def test_response_timeout_after_ack_does_not_resend_request():
    transport = FakeTransport([encode_frame(DATA_TYPE_ACK, 1), None])
    session = ProtocolSession(transport, retries=2)

    with pytest.raises(ProtocolTimeoutError, match="response"):
        session.request(DATA_TYPE_MDR, b"\x00")

    assert len(transport.sent) == 1


def test_request_sequence_advances_after_ack_even_when_response_times_out():
    transport = FakeTransport(
        [
            encode_frame(DATA_TYPE_ACK, 1),
            None,
            encode_frame(DATA_TYPE_ACK, 0),
            encode_frame(DATA_TYPE_MDR, 0, b"\x03"),
        ]
    )
    session = ProtocolSession(transport)

    with pytest.raises(ProtocolTimeoutError, match="response"):
        session.request(DATA_TYPE_MDR, b"\x00")
    assert session.request(DATA_TYPE_MDR, b"\x02").payload == b"\x03"

    requests = [
        frame
        for frame in map(decode_frame, transport.sent)
        if frame.data_type == DATA_TYPE_MDR
    ]
    assert [frame.seq for frame in requests] == [0, 1]


def test_closed_transport_error_is_preserved():
    session = ProtocolSession(FakeTransport([b""]))

    with pytest.raises(ConnectionError, match="closed"):
        session.request(DATA_TYPE_MDR, b"\x00")


def test_successful_requests_toggle_sequence_between_zero_and_one():
    transport = FakeTransport(
        [
            encode_frame(DATA_TYPE_ACK, 1),
            encode_frame(DATA_TYPE_MDR, 1, b"\x01"),
            encode_frame(DATA_TYPE_ACK, 0),
            encode_frame(DATA_TYPE_MDR, 0, b"\x03"),
        ]
    )
    session = ProtocolSession(transport)

    session.request(DATA_TYPE_MDR, b"\x00")
    session.request(DATA_TYPE_MDR, b"\x02")

    sent = [decode_frame(raw) for raw in transport.sent]
    request_seqs = [frame.seq for frame in sent if frame.data_type == DATA_TYPE_MDR]
    assert request_seqs == [0, 1]
