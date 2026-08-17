from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from typing import Protocol

from sonus.protocol.framing import DATA_TYPE_ACK, Frame, FrameStreamDecoder, encode_frame


class ProtocolTimeoutError(Exception):
    """Raised when the ACK or response stage exceeds its timeout."""


class _Transport(Protocol):
    def send(self, data: bytes) -> None: ...
    def recv(self, bufsize: int, timeout: float) -> bytes: ...


class ProtocolSession:
    def __init__(self, transport: _Transport, timeout: float = 2.0, retries: int = 2) -> None:
        self._transport = transport
        self._timeout = timeout
        self._retries = retries
        self._seq = 0
        self._decoder = FrameStreamDecoder()
        self._incoming: deque[Frame] = deque()
        self._notifications: list[Frame] = []

    def _next_frame(self, deadline: float) -> Frame:
        while not self._incoming:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("protocol stage timed out")
            raw = self._transport.recv(bufsize=4096, timeout=remaining)
            if not raw:
                raise ConnectionError("RFCOMM connection closed")
            self._incoming.extend(self._decoder.feed(raw))
        return self._incoming.popleft()

    def _acknowledge(self, frame: Frame) -> None:
        self._transport.send(encode_frame(DATA_TYPE_ACK, 1 - frame.seq))

    def _route_data(
        self,
        frame: Frame,
        matcher: Callable[[Frame], bool] | None,
        candidate: Frame | None,
    ) -> Frame | None:
        self._acknowledge(frame)
        if candidate is None and (matcher is None or matcher(frame)):
            return frame
        self._notifications.append(frame)
        return candidate

    def request(
        self,
        data_type: int,
        payload: bytes = b"",
        *,
        response_matcher: Callable[[Frame], bool] | None = None,
    ) -> Frame:
        request_seq = self._seq
        encoded = encode_frame(data_type, request_seq, payload)
        expected_ack_seq = 1 - request_seq
        candidate: Frame | None = None
        ack_received = False

        for _ in range(self._retries + 1):
            self._transport.send(encoded)
            deadline = time.monotonic() + self._timeout
            while True:
                try:
                    frame = self._next_frame(deadline)
                except TimeoutError:
                    break
                if frame.data_type == DATA_TYPE_ACK:
                    if frame.seq == expected_ack_seq and not frame.payload:
                        ack_received = True
                else:
                    candidate = self._route_data(frame, response_matcher, candidate)
                if ack_received and not self._incoming:
                    break
            if ack_received:
                break

        if not ack_received:
            raise ProtocolTimeoutError("ACK timeout after request retries")

        # 헤드셋은 ACK한 요청을 소비한 것으로 간주하므로 응답 유무와 관계없이 번호를 넘긴다.
        self._seq = 1 - self._seq

        if candidate is None:
            deadline = time.monotonic() + self._timeout
            while candidate is None:
                try:
                    frame = self._next_frame(deadline)
                except TimeoutError as error:
                    raise ProtocolTimeoutError("response timeout after ACK") from error
                if frame.data_type == DATA_TYPE_ACK:
                    continue
                candidate = self._route_data(frame, response_matcher, candidate)

        while self._incoming:
            frame = self._incoming.popleft()
            if frame.data_type != DATA_TYPE_ACK:
                self._route_data(frame, response_matcher, candidate)

        return candidate

    def pop_notifications(self) -> list[Frame]:
        notifications = self._notifications.copy()
        self._notifications.clear()
        return notifications
