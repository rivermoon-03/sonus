from sonus.cli.probe import run_probe
from sonus.protocol.framing import DATA_TYPE_MDR, Frame


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, connection):
        self.connection = connection

    def request(self, data_type, payload, *, response_matcher):
        assert data_type == DATA_TYPE_MDR
        assert payload == b"\x00\x00"
        response = Frame(DATA_TYPE_MDR, 1, bytes.fromhex("0100030030320000"))
        assert response_matcher(response)
        return response


def test_run_probe_reports_channel_and_protocol_payload():
    connection = FakeConnection()

    result = run_probe(
        "58:18:62:1F:C9:CB",
        "956c7b26-d49a-4ba8-b03f-b17d393cb6e2",
        find_channel=lambda mac, uuid: 9,
        connect_fn=lambda mac, channel: connection,
        session_factory=FakeSession,
    )

    assert "channel 9" in result
    assert "0100030030320000" in result
    assert connection.closed
