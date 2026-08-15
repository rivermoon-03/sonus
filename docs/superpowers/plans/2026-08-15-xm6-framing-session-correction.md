# XM6 데이터 형식·수신 처리·응답 흐름 교정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** WH-1000XM6에서 실측한 MDR 통신 데이터 형식으로 인코더와 해석기를 교체하고, RFCOMM으로 나뉘거나 합쳐져 들어오는 데이터와 ACK·비동기 알림을 안정적으로 처리한다.

**Architecture:** `framing.py`는 소켓을 모르는 데이터 묶음 인코더·해석기와 조각난 수신 데이터 재조립기를 제공한다. `session.py`는 blocking transport 위에서 ACK와 응답을 구분하며, 테스트 CLI는 이 세션을 사용해 protocol-info를 조회한다.

**Tech Stack:** Python 3.11+, stdlib `socket`/`collections`/`time`, `pytest`, `uv`, BlueZ RFCOMM

## Global Constraints

- 작업 브랜치는 `feat/docs-and-structure`이며 격리 worktree에서 실행한다.
- `transport/`와 `protocol/`은 PyQt6를 import하지 않는다.
- 데이터 묶음의 바이트 구성은 `data_type(1) + seq(1) + length(4, big-endian) + payload + checksum(1)`이다.
- checksum은 START/END를 제외한 unescaped body의 바이트 합 modulo 256이다.
- `0x3C`, `0x3D`, `0x3E`는 각각 `0x3D 0x2C`, `0x3D 0x2D`, `0x3D 0x2E`로 escape한다.
- ACK data type은 `0x01`, 일반 MDR data type은 `0x0C`, 두 번째 MDR data type은 `0x0E`다.
- 기본 `pytest`는 하드웨어 없이 통과해야 하며 실기기 테스트는 `hardware` marker로 분리한다.
- 모든 새 동작은 실패하는 테스트를 먼저 확인한 뒤 구현한다.
- 커밋 제목과 본문은 한국어로 작성한다.

---

### Task 1: 실측 통신 데이터 형식 적용

**Files:**
- Modify: `src/sonus/protocol/framing.py`
- Replace: `tests/unit/test_framing.py`

**Interfaces:**
- Produces: `Frame(data_type: int, seq: int, payload: bytes)`
- Produces: `encode_frame(data_type: int, seq: int, payload: bytes = b"") -> bytes`
- Produces: `decode_frame(raw: bytes) -> Frame`
- Produces constants: `DATA_TYPE_ACK`, `DATA_TYPE_MDR`, `DATA_TYPE_MDR_NO2`
- Raises: `FrameFormatError`, `FrameChecksumError`

- [ ] **Step 1: 실측 XM6 데이터로 테스트 교체**

```python
import json
from pathlib import Path

import pytest

from sonus.protocol.framing import (
    DATA_TYPE_ACK,
    DATA_TYPE_MDR,
    Frame,
    FrameChecksumError,
    FrameFormatError,
    decode_frame,
    encode_frame,
)

CAPTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "captures"
    / "2026-08-15-xm6-protocol-info.jsonl"
)


def _captures() -> list[dict[str, str]]:
    return [json.loads(line) for line in CAPTURE.read_text().splitlines()]


def test_encode_matches_observed_protocol_info_request():
    assert encode_frame(DATA_TYPE_MDR, 0, b"\x00\x00") == bytes.fromhex(
        "3e0c000000000200000e3c"
    )


def test_decode_matches_observed_ack_and_response():
    records = _captures()
    ack = decode_frame(bytes.fromhex(records[1]["hex"]))
    response = decode_frame(bytes.fromhex(records[2]["hex"]))

    assert ack == Frame(data_type=DATA_TYPE_ACK, seq=1, payload=b"")
    assert response == Frame(
        data_type=DATA_TYPE_MDR,
        seq=1,
        payload=bytes.fromhex("0100030030320000"),
    )


def test_round_trip_escapes_all_special_bytes():
    payload = bytes([0x3C, 0x3D, 0x3E])
    encoded = encode_frame(DATA_TYPE_MDR, 0, payload)

    assert b"\x3d\x2c" in encoded
    assert b"\x3d\x2d" in encoded
    assert b"\x3d\x2e" in encoded
    assert decode_frame(encoded).payload == payload


@pytest.mark.parametrize("data_type, seq", [(-1, 0), (256, 0), (0, -1), (0, 256)])
def test_encode_rejects_byte_fields_out_of_range(data_type, seq):
    with pytest.raises(FrameFormatError):
        encode_frame(data_type, seq)


def test_decode_rejects_truncated_escape():
    with pytest.raises(FrameFormatError, match="escape"):
        decode_frame(b"\x3e\x0c\x00\x00\x00\x00\x00\x3d\x3c")


def test_decode_rejects_declared_length_mismatch_and_trailing_bytes():
    valid = bytearray(encode_frame(DATA_TYPE_MDR, 0, b"\x00"))
    valid[-1:-1] = b"\x00"
    with pytest.raises(FrameFormatError, match="length"):
        decode_frame(bytes(valid))


def test_decode_rejects_bad_checksum():
    raw = bytearray(encode_frame(DATA_TYPE_MDR, 0, b"\x00"))
    raw[-2] ^= 0x01
    with pytest.raises(FrameChecksumError):
        decode_frame(bytes(raw))
```

- [ ] **Step 2: 새 데이터 형식 테스트가 실패하는지 확인**

Run: `.venv/bin/pytest tests/unit/test_framing.py -v`

Expected: failures because `Frame` has `msg_type`, the length is one byte, escaping uses XOR `0x20`, and checksum uses two's complement.

- [ ] **Step 3: 인코더와 해석기를 실측 형식으로 교체**

```python
"""Pure frame codec for the Sony MDR protocol observed on WH-1000XM6."""
from __future__ import annotations

from dataclasses import dataclass

START = 0x3E
END = 0x3C
ESCAPE = 0x3D
DATA_TYPE_ACK = 0x01
DATA_TYPE_MDR = 0x0C
DATA_TYPE_MDR_NO2 = 0x0E
_SPECIAL_BYTES = (START, END, ESCAPE)
_ESCAPED_BYTES = {0x2C: END, 0x2D: ESCAPE, 0x2E: START}


class FrameFormatError(Exception):
    """Raised when raw bytes do not form one complete valid frame."""


class FrameChecksumError(Exception):
    """Raised when a decoded frame has an invalid checksum."""


@dataclass(frozen=True)
class Frame:
    data_type: int
    seq: int
    payload: bytes


def _validate_byte(name: str, value: int) -> None:
    if not isinstance(value, int) or not 0 <= value <= 0xFF:
        raise FrameFormatError(f"{name} must be an integer from 0 to 255")


def _checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def _stuff(data: bytes) -> bytes:
    out = bytearray()
    for byte in data:
        if byte in _SPECIAL_BYTES:
            out.extend((ESCAPE, byte - 0x10))
        else:
            out.append(byte)
    return bytes(out)


def _unstuff(data: bytes) -> bytes:
    out = bytearray()
    index = 0
    while index < len(data):
        byte = data[index]
        if byte != ESCAPE:
            out.append(byte)
            index += 1
            continue
        if index + 1 >= len(data):
            raise FrameFormatError("truncated escape sequence")
        escaped = data[index + 1]
        if escaped not in _ESCAPED_BYTES:
            raise FrameFormatError(f"invalid escaped byte: {escaped:#x}")
        out.append(_ESCAPED_BYTES[escaped])
        index += 2
    return bytes(out)


def encode_frame(data_type: int, seq: int, payload: bytes = b"") -> bytes:
    _validate_byte("data_type", data_type)
    _validate_byte("seq", seq)
    if len(payload) > 0xFFFFFFFF:
        raise FrameFormatError("payload is too large for a 4-byte length")
    body = bytes([data_type, seq]) + len(payload).to_bytes(4, "big") + payload
    body += bytes([_checksum(body)])
    return bytes([START]) + _stuff(body) + bytes([END])


def decode_frame(raw: bytes) -> Frame:
    if len(raw) < 2 or raw[0] != START or raw[-1] != END:
        raise FrameFormatError("frame missing START/END markers")
    body = _unstuff(raw[1:-1])
    if len(body) < 7:
        raise FrameFormatError("frame body too short")

    data_type, seq = body[0], body[1]
    length = int.from_bytes(body[2:6], "big")
    expected_size = 6 + length + 1
    if len(body) != expected_size:
        raise FrameFormatError(
            f"frame length mismatch: declared {length}, body has {len(body) - 7} payload bytes"
        )

    received_checksum = body[-1]
    expected_checksum = _checksum(body[:-1])
    if received_checksum != expected_checksum:
        raise FrameChecksumError(
            f"checksum mismatch: expected {expected_checksum:#x}, got {received_checksum:#x}"
        )
    return Frame(data_type=data_type, seq=seq, payload=body[6:-1])
```

- [ ] **Step 4: 데이터 형식 테스트와 전체 단위 테스트 실행**

Run: `.venv/bin/pytest tests/unit/test_framing.py -v`

Expected: all framing tests pass.

Run: `.venv/bin/pytest -v`

Expected: session and CLI tests fail only where they still call the old `msg_type` API; record these as expected downstream failures.

- [ ] **Step 5: 데이터 형식 교정 커밋**

```bash
git add src/sonus/protocol/framing.py tests/unit/test_framing.py
git commit -m "fix: XM6 실측 데이터 형식 적용" \
  -m "4바이트 길이, 합산 checksum과 실제 특수 바이트 처리 규칙을 적용한다." \
  -m "실기기 protocol-info 캡처를 테스트 자료로 검증한다."
```

---

### Task 2: RFCOMM 수신 데이터 재조립

**Files:**
- Modify: `src/sonus/protocol/framing.py`
- Create: `tests/unit/test_stream_decoder.py`

**Interfaces:**
- Consumes: `decode_frame(raw: bytes) -> Frame`
- Produces: `FrameStreamDecoder(max_frame_size: int = 4096)`
- Produces: `FrameStreamDecoder.feed(data: bytes) -> list[Frame]`
- Produces: `FrameStreamDecoder.reset() -> None`

- [ ] **Step 1: 조각나거나 합쳐진 수신 데이터의 실패 테스트 작성**

```python
import pytest

from sonus.protocol.framing import (
    DATA_TYPE_ACK,
    DATA_TYPE_MDR,
    FrameChecksumError,
    FrameFormatError,
    FrameStreamDecoder,
    encode_frame,
)


def test_feed_reassembles_frame_at_every_split_boundary():
    raw = encode_frame(DATA_TYPE_MDR, 0, b"\x00\x00")
    for split in range(1, len(raw)):
        decoder = FrameStreamDecoder()
        assert decoder.feed(raw[:split]) == []
        frames = decoder.feed(raw[split:])
        assert [frame.payload for frame in frames] == [b"\x00\x00"]


def test_feed_returns_multiple_frames_from_one_chunk():
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, bytes.fromhex("0100030030320000"))
    frames = FrameStreamDecoder().feed(ack + response)

    assert [frame.data_type for frame in frames] == [DATA_TYPE_ACK, DATA_TYPE_MDR]


def test_feed_discards_noise_before_start_marker():
    raw = encode_frame(DATA_TYPE_ACK, 1)
    assert FrameStreamDecoder().feed(b"noise" + raw)[0].data_type == DATA_TYPE_ACK


def test_invalid_frame_is_consumed_and_next_frame_can_be_recovered():
    invalid = bytearray(encode_frame(DATA_TYPE_MDR, 0, b"\x00"))
    invalid[-2] ^= 0x01
    valid = encode_frame(DATA_TYPE_ACK, 1)
    decoder = FrameStreamDecoder()

    with pytest.raises(FrameChecksumError):
        decoder.feed(bytes(invalid) + valid)

    assert decoder.feed(b"")[0].data_type == DATA_TYPE_ACK


def test_incomplete_frame_over_limit_resets_buffer():
    decoder = FrameStreamDecoder(max_frame_size=12)
    with pytest.raises(FrameFormatError, match="maximum"):
        decoder.feed(b"\x3e" + b"\x00" * 12)

    assert decoder.feed(encode_frame(DATA_TYPE_ACK, 1))[0].data_type == DATA_TYPE_ACK
```

- [ ] **Step 2: 수신 데이터 재조립 테스트가 실패하는지 확인**

Run: `.venv/bin/pytest tests/unit/test_stream_decoder.py -v`

Expected: import failure because `FrameStreamDecoder` does not exist.

- [ ] **Step 3: `decode_frame` 아래에 수신 데이터 재조립기 추가**

```python
class FrameStreamDecoder:
    """Incrementally reconstruct MDR frames from RFCOMM byte chunks."""

    def __init__(self, max_frame_size: int = 4096) -> None:
        if max_frame_size < 2:
            raise ValueError("max_frame_size must be at least 2")
        self._max_frame_size = max_frame_size
        self._buffer = bytearray()

    def reset(self) -> None:
        self._buffer.clear()

    def feed(self, data: bytes) -> list[Frame]:
        self._buffer.extend(data)
        frames: list[Frame] = []
        while True:
            try:
                start = self._buffer.index(START)
            except ValueError:
                self._buffer.clear()
                return frames

            if start:
                del self._buffer[:start]

            try:
                end = self._buffer.index(END, 1)
            except ValueError:
                if len(self._buffer) > self._max_frame_size:
                    self._buffer.clear()
                    raise FrameFormatError("packed frame exceeds maximum size")
                return frames

            raw = bytes(self._buffer[: end + 1])
            del self._buffer[: end + 1]
            if len(raw) > self._max_frame_size:
                raise FrameFormatError("packed frame exceeds maximum size")
            frames.append(decode_frame(raw))
```

- [ ] **Step 4: 수신 데이터와 형식 테스트 실행**

Run: `.venv/bin/pytest tests/unit/test_stream_decoder.py tests/unit/test_framing.py -v`

Expected: all tests pass.

- [ ] **Step 5: 수신 데이터 재조립 기능 커밋**

```bash
git add src/sonus/protocol/framing.py tests/unit/test_stream_decoder.py
git commit -m "feat: RFCOMM 수신 데이터 재조립" \
  -m "나뉘어 들어오거나 한꺼번에 들어온 데이터 묶음을 내부 저장 공간에서 이어 붙인다." \
  -m "손상된 데이터 이후 다시 경계를 찾는 동작과 저장 크기 제한을 검증한다."
```

---

### Task 3: ACK·응답·비동기 알림 세션 라우팅

**Files:**
- Replace: `src/sonus/protocol/session.py`
- Replace: `tests/unit/test_session.py`

**Interfaces:**
- Consumes: `Frame`, `FrameStreamDecoder`, `encode_frame`, `DATA_TYPE_ACK`
- Produces: `ProtocolSession.request(data_type, payload=b"", *, response_matcher=None) -> Frame`
- Produces: `ProtocolSession.pop_notifications() -> list[Frame]`
- Raises: `ProtocolTimeoutError`

- [ ] **Step 1: Replace session tests with stream-aware behavior tests**

```python
from collections import deque

import pytest

from sonus.protocol.framing import (
    DATA_TYPE_ACK,
    DATA_TYPE_MDR,
    decode_frame,
    encode_frame,
)
from sonus.protocol.session import ProtocolSession, ProtocolTimeoutError


class FakeTransport:
    def __init__(self, chunks):
        self.sent = []
        self._chunks = deque(chunks)

    def send(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, bufsize: int, timeout: float) -> bytes:
        if not self._chunks:
            raise TimeoutError("no scripted data")
        chunk = self._chunks.popleft()
        if chunk is None:
            raise TimeoutError("scripted timeout")
        return chunk


def test_request_handles_ack_and_response_in_one_recv():
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01\x00")
    transport = FakeTransport([ack + response])

    result = ProtocolSession(transport).request(DATA_TYPE_MDR, b"\x00\x00")

    assert result.payload == b"\x01\x00"
    assert decode_frame(transport.sent[0]).payload == b"\x00\x00"
    assert decode_frame(transport.sent[1]).data_type == DATA_TYPE_ACK
    assert decode_frame(transport.sent[1]).seq == 0


def test_request_queues_notification_before_matching_response():
    notification = encode_frame(DATA_TYPE_MDR, 1, b"\xc9\x01")
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01\x00")
    transport = FakeTransport([notification, ack, response])
    session = ProtocolSession(transport)

    result = session.request(
        DATA_TYPE_MDR,
        b"\x00\x00",
        response_matcher=lambda frame: frame.payload.startswith(b"\x01"),
    )

    assert result.payload == b"\x01\x00"
    assert [frame.payload for frame in session.pop_notifications()] == [b"\xc9\x01"]
    assert session.pop_notifications() == []
    sent = [decode_frame(raw) for raw in transport.sent]
    assert [(frame.data_type, frame.seq) for frame in sent[1:]] == [
        (DATA_TYPE_ACK, 0),
        (DATA_TYPE_ACK, 0),
    ]


def test_request_retries_only_while_waiting_for_ack():
    ack = encode_frame(DATA_TYPE_ACK, 1)
    response = encode_frame(DATA_TYPE_MDR, 1, b"\x01")
    transport = FakeTransport([None, ack, response])

    ProtocolSession(transport, retries=1).request(DATA_TYPE_MDR, b"\x00")

    requests = [decode_frame(raw) for raw in transport.sent if decode_frame(raw).data_type != DATA_TYPE_ACK]
    assert len(requests) == 2
    assert requests[0] == requests[1]


def test_response_timeout_after_ack_does_not_resend_request():
    transport = FakeTransport([encode_frame(DATA_TYPE_ACK, 1), None])
    session = ProtocolSession(transport, retries=2)

    with pytest.raises(ProtocolTimeoutError, match="response"):
        session.request(DATA_TYPE_MDR, b"\x00")

    requests = [decode_frame(raw) for raw in transport.sent]
    assert len(requests) == 1


def test_closed_transport_error_is_preserved():
    session = ProtocolSession(FakeTransport([b""]))

    with pytest.raises(ConnectionError, match="closed"):
        session.request(DATA_TYPE_MDR, b"\x00")


def test_successful_requests_toggle_sequence_between_zero_and_one():
    transport = FakeTransport(
        [
            encode_frame(DATA_TYPE_ACK, 1),
            encode_frame(DATA_TYPE_MDR, 1, b"\x01"),
            encode_frame(DATA_TYPE_ACK, 0),
            encode_frame(DATA_TYPE_MDR, 0, b"\x03"),
        ]
    )
    session = ProtocolSession(transport)

    session.request(DATA_TYPE_MDR, b"\x00")
    session.request(DATA_TYPE_MDR, b"\x02")

    sent = [decode_frame(raw) for raw in transport.sent]
    request_seqs = [frame.seq for frame in sent if frame.data_type == DATA_TYPE_MDR]
    assert request_seqs == [0, 1]
```

- [ ] **Step 2: Run session tests and verify RED**

Run: `.venv/bin/pytest tests/unit/test_session.py -v`

Expected: failures because the current session decodes one `recv()` as one frame, does not emit ACK, and uses the old method signature.

- [ ] **Step 3: Implement the stream-aware session**

```python
from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from typing import Protocol

from sonus.protocol.framing import (
    DATA_TYPE_ACK,
    Frame,
    FrameStreamDecoder,
    encode_frame,
)


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
                    if frame.seq == expected_ack_seq:
                        ack_received = True
                        break
                    continue
                candidate = self._route_data(frame, response_matcher, candidate)
            if ack_received:
                break

        if not ack_received:
            raise ProtocolTimeoutError("ACK timeout after request retries")

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

        self._seq = 1 - self._seq
        return candidate

    def pop_notifications(self) -> list[Frame]:
        notifications = self._notifications.copy()
        self._notifications.clear()
        return notifications
```

- [ ] **Step 4: Run session, stream and framing tests**

Run: `.venv/bin/pytest tests/unit/test_session.py tests/unit/test_stream_decoder.py tests/unit/test_framing.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit the session correction**

```bash
git add src/sonus/protocol/session.py tests/unit/test_session.py
git commit -m "feat: ACK와 비동기 알림 처리" \
  -m "요청 ACK와 응답을 구분하고 수신 data frame에 즉시 ACK한다." \
  -m "요청 사이에 들어온 알림을 순서대로 보관하며 안전한 재시도 범위를 적용한다."
```

---

### Task 4: 교정 세션을 CLI에 연결

**Files:**
- Modify: `src/sonus/cli/probe.py`
- Modify: `src/sonus/cli/send.py`
- Modify: `src/sonus/cli/main.py`
- Replace: `tests/unit/test_cli_probe.py`
- Replace: `tests/unit/test_cli_send.py`
- Create: `tests/unit/test_cli_main.py`

**Interfaces:**
- Consumes: `ProtocolSession.request`, `DATA_TYPE_MDR`
- Produces: `run_probe(...) -> str` containing channel and protocol payload
- Produces: `run_send(..., data_type: int, payload_hex: str, ...) -> str`
- Produces: `main(argv=None) -> int` with user-facing error conversion

- [ ] **Step 1: Write failing probe and send tests with injected sessions**

```python
# tests/unit/test_cli_probe.py
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
```

```python
# tests/unit/test_cli_send.py
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
```

- [ ] **Step 2: Write a failing top-level error presentation test**

```python
# tests/unit/test_cli_main.py
from sonus.cli import main as cli_main
from sonus.protocol.session import ProtocolTimeoutError


def test_main_converts_timeout_to_short_user_message(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise ProtocolTimeoutError("internal detail")

    monkeypatch.setattr(cli_main, "run_probe", fail)
    result = cli_main.main(["probe", "--mac", "58:18:62:1F:C9:CB"])

    captured = capsys.readouterr()
    assert result == 1
    assert "응답 시간이 초과" in captured.err
    assert "Traceback" not in captured.err
    assert "internal detail" not in captured.err
```

- [ ] **Step 3: Run CLI tests and verify RED**

Run: `.venv/bin/pytest tests/unit/test_cli_probe.py tests/unit/test_cli_send.py tests/unit/test_cli_main.py -v`

Expected: failures because probe does not create a session, send still accepts `msg_type`, and main lets exceptions escape.

- [ ] **Step 4: Update probe and send implementations**

```python
# src/sonus/cli/probe.py
from __future__ import annotations

from sonus.protocol.framing import DATA_TYPE_MDR
from sonus.protocol.session import ProtocolSession
from sonus.transport.rfcomm import connect_with_retries as default_connect
from sonus.transport.sdp import find_rfcomm_channel as default_find_channel


def run_probe(
    mac: str,
    service_uuid: str,
    *,
    find_channel=default_find_channel,
    connect_fn=default_connect,
    session_factory=ProtocolSession,
) -> str:
    channel = find_channel(mac, service_uuid)
    connection = connect_fn(mac, channel)
    try:
        session = session_factory(connection)
        response = session.request(
            DATA_TYPE_MDR,
            b"\x00\x00",
            response_matcher=lambda frame: (
                frame.data_type == DATA_TYPE_MDR
                and frame.payload.startswith(b"\x01")
            ),
        )
        return (
            f"Found RFCOMM channel {channel} for {mac}; "
            f"protocol_info={response.payload.hex()}"
        )
    finally:
        connection.close()
```

```python
# src/sonus/cli/send.py
from __future__ import annotations

from sonus.protocol.session import ProtocolSession
from sonus.transport.rfcomm import connect_with_retries as default_connect


def run_send(
    mac: str,
    channel: int,
    *,
    data_type: int,
    payload_hex: str,
    connect_fn=default_connect,
    session_factory=ProtocolSession,
) -> str:
    connection = connect_fn(mac, channel)
    try:
        session = session_factory(connection)
        response = session.request(data_type=data_type, payload=bytes.fromhex(payload_hex))
        return (
            f"Response: data_type={response.data_type:#04x} "
            f"seq={response.seq} payload={response.payload.hex()}"
        )
    finally:
        connection.close()
```

- [ ] **Step 5: Update parser naming and error conversion in `main.py`**

Change the send argument and dispatch to `data_type`:

```python
send_parser.add_argument(
    "--type",
    type=lambda value: int(value, 0),
    required=True,
    dest="data_type",
    help="MDR frame data type, for example 0x0c",
)
```

Add imports and the error formatter:

```python
from sonus.protocol.framing import FrameChecksumError, FrameFormatError
from sonus.protocol.session import ProtocolTimeoutError
from sonus.transport.sdp import SdpLookupError


def _error_message(error: Exception) -> str:
    if isinstance(error, ProtocolTimeoutError):
        return "헤드셋 응답 시간이 초과되었습니다."
    if isinstance(error, SdpLookupError):
        return "헤드셋의 RFCOMM 채널을 찾지 못했습니다."
    if isinstance(error, (FrameFormatError, FrameChecksumError)):
        return "헤드셋에서 올바르지 않은 프레임을 받았습니다."
    if isinstance(error, ValueError):
        return "입력값이 올바르지 않습니다."
    return "Bluetooth 연결에 실패했습니다."
```

Wrap command dispatch and update send invocation:

```python
try:
    if args.command == "probe":
        print(run_probe(args.mac, args.service_uuid))
    elif args.command == "sniff":
        try:
            count = run_sniff(args.mac, args.channel, args.out)
        except KeyboardInterrupt:
            print("stopped")
            return 0
        print(f"logged {count} frames to {args.out}")
    elif args.command == "send":
        print(
            run_send(
                args.mac,
                args.channel,
                data_type=args.data_type,
                payload_hex=args.payload,
            )
        )
except (OSError, ValueError, SdpLookupError, ProtocolTimeoutError, FrameFormatError, FrameChecksumError) as error:
    print(f"오류: {_error_message(error)}", file=sys.stderr)
    return 1
return 0
```

- [ ] **Step 6: Run all CLI tests**

Run: `.venv/bin/pytest tests/unit/test_cli_probe.py tests/unit/test_cli_send.py tests/unit/test_cli_main.py tests/unit/test_cli_sniff.py -v`

Expected: all tests pass.

- [ ] **Step 7: Commit the CLI integration**

```bash
git add src/sonus/cli tests/unit/test_cli_probe.py tests/unit/test_cli_send.py tests/unit/test_cli_main.py
git commit -m "feat: 교정된 XM6 통신을 테스트 CLI에 연결" \
  -m "probe에서 protocol-info를 조회하고 send의 type 의미를 명확히 한다." \
  -m "예상 가능한 통신 오류를 짧은 사용자 메시지로 변환한다."
```

---

### Task 5: 문서 갱신과 실기기 회귀 검증

**Files:**
- Modify: `docs/protocol/README.md`
- Modify: `README.md`
- Create: `tests/hardware/test_protocol_probe.py`

**Interfaces:**
- Consumes: `run_probe(mac, service_uuid) -> str`
- Produces: `pytest -m hardware`로 실행되는 protocol-info smoke test

- [ ] **Step 1: Add the hardware-marked probe test**

```python
import pytest

from sonus.cli.main import DEFAULT_SERVICE_UUID
from sonus.cli.probe import run_probe

XM6_MAC = "58:18:62:1F:C9:CB"


@pytest.mark.hardware
def test_xm6_protocol_info_probe():
    result = run_probe(XM6_MAC, DEFAULT_SERVICE_UUID)

    assert "channel 9" in result
    assert "protocol_info=0100030030320000" in result
```

- [ ] **Step 2: Run default tests and confirm the hardware test is excluded**

Run: `.venv/bin/pytest -v`

Expected: every unit test passes and `test_xm6_protocol_info_probe` is deselected by the default `not hardware` marker expression.

- [ ] **Step 3: Update protocol documentation status**

In `docs/protocol/README.md`:

- Change the heading from `implementation correction pending` to `implemented and verified`.
- State that `framing.py` now implements the observed layout.
- Add a verification entry containing the successful CLI command:

```markdown
### 2026-08-15 — 교정 구현 회귀 검증

- `sonus probe --mac 58:18:62:1F:C9:CB`가 RFCOMM channel 9를 탐색했다.
- 요청 `3e0c000000000200000e3c`에 ACK와 protocol-info 응답을 수신했다.
- 응답 payload는 `0100030030320000`이며 checksum 검증을 통과했다.
- ACK와 응답의 병합 수신, 큰 알림의 분할 수신을 단위 테스트로 고정했다.
```

- [ ] **Step 4: Update README current features and execution output**

In `README.md`, replace the pending stream item with:

```markdown
- XM6 MDR 데이터 묶음 생성·해석과 조각난 수신 데이터 재조립
- ACK, 요청 응답과 비동기 알림 세션 처리
```

Add after the probe command:

```markdown
정상 연결 시 RFCOMM channel과 protocol-info payload가 출력된다.
```

- [ ] **Step 5: Run the full unit suite and static sanity checks**

Run: `.venv/bin/pytest -v`

Expected: all non-hardware tests pass.

Run: `.venv/bin/python -m compileall -q src tests`

Expected: exit code 0 with no output.

Run: `git diff --check`

Expected: exit code 0 with no output.

- [ ] **Step 6: Run the hardware regression against the powered-on XM6**

Run: `.venv/bin/pytest -m hardware tests/hardware/test_protocol_probe.py -v`

Expected: `test_xm6_protocol_info_probe` passes and reports no timeout or frame error.

- [ ] **Step 7: Commit docs and hardware regression**

```bash
git add README.md docs/protocol/README.md tests/hardware/test_protocol_probe.py
git commit -m "test: XM6 정보 조회 회귀 테스트 추가" \
  -m "교정된 데이터 형식과 응답 처리를 실제 헤드셋에서 확인한다." \
  -m "현재 지원 범위와 실행 결과를 README와 프로토콜 문서에 반영한다."
```

---

## Self-Review Notes

- **Spec coverage:** Task 1은 통신 데이터 형식, Task 2는 나뉘거나 합쳐진 RFCOMM 데이터 처리, Task 3은 ACK·응답·알림, Task 4는 테스트 CLI와 오류 표시, Task 5는 문서와 실기기 완료 기준을 다룬다.
- **Scope:** payload registry, device API, asyncio와 GUI는 설계대로 제외했다.
- **Type consistency:** 모든 계층은 `Frame.data_type`, `encode_frame(data_type, seq, payload)`, `ProtocolSession.request(data_type, payload, response_matcher=...)`를 동일하게 사용한다.
- **Safety:** ACK 이후 response timeout은 요청을 재전송하지 않아 상태 변경 명령의 중복 적용을 막는다.
