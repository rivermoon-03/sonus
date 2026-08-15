# tests/unit/test_cli_send.py
from sonus.protocol.framing import encode_frame
from sonus.cli.send import run_send


class _FakeConnection:
    def __init__(self, response: bytes):
        self._response = response
        self.sent = []

    def send(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, bufsize: int, timeout: float) -> bytes:
        return self._response

    def close(self) -> None:
        pass


def test_run_send_reports_response_payload_hex():
    response = encode_frame(seq=0, msg_type=0x81, payload=b"\xde\xad")
    connection = _FakeConnection(response)

    result = run_send(
        "58:18:62:1F:C9:CB",
        8,
        msg_type=0x01,
        payload_hex="aabb",
        connect_fn=lambda mac, channel, timeout=10.0: connection,
    )

    assert "81" in result  # response msg_type shown
    assert "dead" in result.lower()  # response payload shown
    sent_payload = bytes.fromhex("aabb")
    assert sent_payload in b"".join(connection.sent)
