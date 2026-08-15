import pytest

from sonus.protocol.framing import Frame, encode_frame
from sonus.protocol.session import ProtocolSession, ProtocolTimeoutError


class FakeTransport:
    """Records sent bytes; returns scripted responses or raises TimeoutError."""

    def __init__(self, responses):
        self.sent = []
        self._responses = list(responses)

    def send(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, bufsize: int, timeout: float) -> bytes:
        if not self._responses:
            raise TimeoutError("no more scripted responses")
        response = self._responses.pop(0)
        if response is None:
            raise TimeoutError("scripted timeout")
        return response


def test_request_sends_encoded_frame_with_seq_zero_first():
    transport = FakeTransport([encode_frame(seq=0, msg_type=0x01, payload=b"\xaa")])
    session = ProtocolSession(transport)

    session.request(msg_type=0x02, payload=b"\x01")

    assert len(transport.sent) == 1
    from sonus.protocol.framing import decode_frame

    sent_frame = decode_frame(transport.sent[0])
    assert sent_frame.seq == 0
    assert sent_frame.msg_type == 0x02
    assert sent_frame.payload == b"\x01"


def test_request_increments_sequence_across_calls():
    transport = FakeTransport(
        [
            encode_frame(seq=0, msg_type=0x01, payload=b""),
            encode_frame(seq=1, msg_type=0x01, payload=b""),
        ]
    )
    session = ProtocolSession(transport)

    session.request(msg_type=0x02)
    session.request(msg_type=0x02)

    from sonus.protocol.framing import decode_frame

    seqs = [decode_frame(sent).seq for sent in transport.sent]
    assert seqs == [0, 1]


def test_request_returns_decoded_response_frame():
    transport = FakeTransport([encode_frame(seq=0, msg_type=0x81, payload=b"\x99")])
    session = ProtocolSession(transport)

    response = session.request(msg_type=0x01)

    assert response == Frame(seq=0, msg_type=0x81, payload=b"\x99")


def test_request_retries_on_timeout_then_succeeds():
    transport = FakeTransport([None, encode_frame(seq=0, msg_type=0x81, payload=b"")])
    session = ProtocolSession(transport, retries=2)

    response = session.request(msg_type=0x01)

    assert response.msg_type == 0x81
    assert len(transport.sent) == 2  # resent once after the timeout


def test_request_raises_after_exhausting_retries():
    transport = FakeTransport([None, None])
    session = ProtocolSession(transport, retries=1)

    with pytest.raises(ProtocolTimeoutError):
        session.request(msg_type=0x01)
