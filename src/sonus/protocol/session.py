from __future__ import annotations

from typing import Protocol

from sonus.protocol.framing import Frame, decode_frame, encode_frame


class ProtocolTimeoutError(Exception):
    """Raised when a request gets no valid response within retries * timeout."""


class _Transport(Protocol):
    def send(self, data: bytes) -> None: ...
    def recv(self, bufsize: int, timeout: float) -> bytes: ...


class ProtocolSession:
    def __init__(self, transport: _Transport, timeout: float = 2.0, retries: int = 2) -> None:
        self._transport = transport
        self._timeout = timeout
        self._retries = retries
        self._seq = 0

    def request(self, msg_type: int, payload: bytes = b"") -> Frame:
        seq = self._seq
        self._seq = (self._seq + 1) % 256
        encoded = encode_frame(seq=seq, msg_type=msg_type, payload=payload)

        attempts = self._retries + 1
        last_error: Exception | None = None
        for _ in range(attempts):
            self._transport.send(encoded)
            try:
                raw = self._transport.recv(bufsize=4096, timeout=self._timeout)
                return decode_frame(raw)
            except TimeoutError as error:
                last_error = error
                continue

        raise ProtocolTimeoutError(
            f"no response to msg_type {msg_type:#x} after {attempts} attempts"
        ) from last_error
