from sonus.cli.send import run_send
from sonus.protocol.framing import DATA_TYPE_MDR, Frame


class FakeConnection:
    def close(self):
        pass


class FakeSession:
    def __init__(self, connection):
        pass

    def request(self, data_type, payload):
        assert data_type == DATA_TYPE_MDR
        assert payload == bytes.fromhex("0000")
        return Frame(DATA_TYPE_MDR, 1, b"\x01\x00")


def test_run_send_uses_data_type_and_reports_response():
    result = run_send(
        "58:18:62:1F:C9:CB",
        9,
        data_type=DATA_TYPE_MDR,
        payload_hex="0000",
        connect_fn=lambda mac, channel: FakeConnection(),
        session_factory=FakeSession,
    )

    assert "data_type=0x0c" in result
    assert "payload=0100" in result
