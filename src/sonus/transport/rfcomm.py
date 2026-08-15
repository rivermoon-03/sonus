from __future__ import annotations

import socket
import time
from collections.abc import Callable
from typing import Self


class RfcommConnection:
    """A connected RFCOMM socket to a Bluetooth device."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock

    def send(self, data: bytes) -> None:
        self._sock.sendall(data)

    def recv(self, bufsize: int = 4096, timeout: float | None = None) -> bytes:
        self._sock.settimeout(timeout)
        return self._sock.recv(bufsize)

    def close(self) -> None:
        self._sock.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def connect(mac: str, channel: int, timeout: float = 10.0) -> RfcommConnection:
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    try:
        sock.settimeout(timeout)
        sock.connect((mac, channel))
    except Exception:
        sock.close()
        raise
    return RfcommConnection(sock)


def connect_with_backoff(
    connector: Callable[[], RfcommConnection],
    attempts: int = 3,
    base_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> RfcommConnection:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return connector()
        except Exception as error:  # noqa: BLE001 - re-raised below if exhausted
            last_error = error
            if attempt < attempts - 1:
                sleep(base_delay * (2**attempt))
    assert last_error is not None
    raise last_error


def connect_with_retries(mac: str, channel: int, timeout: float = 10.0) -> RfcommConnection:
    """Connect with exponential backoff (3 attempts, 1s/2s delays)."""
    return connect_with_backoff(
        lambda: connect(mac, channel, timeout),
        sleep=time.sleep,
    )
