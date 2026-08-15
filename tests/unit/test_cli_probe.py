# tests/unit/test_cli_probe.py
from sonus.cli.probe import run_probe


class _FakeConnection:
    def close(self):
        pass


def test_run_probe_reports_channel_and_success():
    def fake_find_channel(mac, service_uuid, timeout=5.0):
        assert mac == "58:18:62:1F:C9:CB"
        return 8

    def fake_connect(mac, channel, timeout=10.0):
        assert channel == 8
        return _FakeConnection()

    result = run_probe(
        "58:18:62:1F:C9:CB",
        "956c7b26-d49a-4ba8-b03f-b17d393cb6e2",
        find_channel=fake_find_channel,
        connect_fn=fake_connect,
    )

    assert "channel 8" in result
    assert "connected" in result.lower()
