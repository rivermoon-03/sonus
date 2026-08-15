from unittest.mock import patch

import pytest

from sonus.transport.rfcomm import connect, connect_with_backoff, connect_with_retries


def test_connect_closes_socket_when_connection_fails():
    with patch("sonus.transport.rfcomm.socket.socket") as socket_factory:
        sock = socket_factory.return_value
        sock.connect.side_effect = ConnectionError("device not found")

        with pytest.raises(ConnectionError, match="device not found"):
            connect("58:18:62:1F:C9:CB", 8)

    sock.close.assert_called_once_with()


def test_connect_closes_socket_when_setting_timeout_fails():
    with patch("sonus.transport.rfcomm.socket.socket") as socket_factory:
        sock = socket_factory.return_value
        sock.settimeout.side_effect = OSError("timeout failed")

        with pytest.raises(OSError, match="timeout failed"):
            connect("58:18:62:1F:C9:CB", 8)

    sock.close.assert_called_once_with()


def test_connect_with_backoff_returns_on_first_success():
    calls = []

    def connector():
        calls.append(1)
        return "connection"

    result = connect_with_backoff(connector, attempts=3, base_delay=1.0, sleep=lambda s: None)

    assert result == "connection"
    assert len(calls) == 1


def test_connect_with_backoff_retries_then_succeeds():
    attempts_made = []

    def connector():
        attempts_made.append(1)
        if len(attempts_made) < 3:
            raise ConnectionError("not ready")
        return "connection"

    sleeps = []
    result = connect_with_backoff(connector, attempts=3, base_delay=1.0, sleep=sleeps.append)

    assert result == "connection"
    assert len(attempts_made) == 3
    assert sleeps == [1.0, 2.0]  # exponential backoff between attempts, none after final success


def test_connect_with_backoff_raises_after_exhausting_attempts():
    def connector():
        raise ConnectionError("device not found")

    with pytest.raises(ConnectionError, match="device not found"):
        connect_with_backoff(connector, attempts=3, base_delay=0.01, sleep=lambda s: None)


def test_connect_with_retries_retries_via_backoff_then_succeeds():
    attempts_made = []

    def fake_connect(mac, channel, timeout):
        attempts_made.append((mac, channel, timeout))
        if len(attempts_made) < 3:
            raise ConnectionError("not ready")
        return "connection"

    with patch("sonus.transport.rfcomm.connect", side_effect=fake_connect), patch(
        "time.sleep"
    ) as mock_sleep:
        result = connect_with_retries("58:18:62:1F:C9:CB", 8, timeout=5.0)

    assert result == "connection"
    assert len(attempts_made) == 3
    assert attempts_made[0] == ("58:18:62:1F:C9:CB", 8, 5.0)
    assert mock_sleep.call_count == 2  # backoff between attempts 1->2 and 2->3


def test_connect_with_retries_raises_after_exhausting_attempts():
    def fake_connect(mac, channel, timeout):
        raise ConnectionError("device not found")

    with patch("sonus.transport.rfcomm.connect", side_effect=fake_connect), patch("time.sleep"):
        with pytest.raises(ConnectionError, match="device not found"):
            connect_with_retries("58:18:62:1F:C9:CB", 8)
