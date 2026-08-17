from __future__ import annotations

from sonus.device.connection import DEFAULT_SERVICE_UUID, open_xm6_device
from sonus.messages.registry import FEATURES


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_open_device_discovers_channel_and_closes_connection():
    connection = FakeConnection()
    lookups = []
    connects = []

    with open_xm6_device(
        "AA:BB:CC:DD:EE:FF",
        find_channel=lambda mac, uuid: lookups.append((mac, uuid)) or 9,
        connect_fn=lambda mac, channel: connects.append((mac, channel)) or connection,
    ) as device:
        assert device.capabilities()[0]["key"] == "protocol"
        assert connection.closed is False

    assert lookups == [("AA:BB:CC:DD:EE:FF", DEFAULT_SERVICE_UUID)]
    assert connects == [("AA:BB:CC:DD:EE:FF", 9)]
    assert connection.closed is True


def test_open_device_uses_explicit_channel_and_custom_features():
    connection = FakeConnection()

    with open_xm6_device(
        "AA",
        12,
        features={"battery": FEATURES["battery"]},
        find_channel=lambda *_: (_ for _ in ()).throw(AssertionError("lookup called")),
        connect_fn=lambda mac, channel: connection,
    ) as device:
        assert [item["key"] for item in device.capabilities()] == ["battery"]


def test_open_device_closes_connection_when_consumer_raises():
    connection = FakeConnection()

    try:
        with open_xm6_device("AA", 9, connect_fn=lambda *_: connection):
            raise RuntimeError("consumer failed")
    except RuntimeError:
        pass

    assert connection.closed is True
