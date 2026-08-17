# Phase 1: 전송 계층, 프로토콜 기반, 테스트 CLI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the transport (RFCOMM + SDP channel discovery) and protocol
(frame codec + ACK/sequencing session) layers, plus a `sonus` CLI (`probe`,
`sniff`, `send`) that lets the user send arbitrary bytes to the real
WH-1000XM6 and observe raw responses — the tool needed to verify the XM6
protocol hypothesis against the actual device.

**Architecture:** Sync, blocking-socket core (`transport/`, `protocol/`).
No asyncio in this phase — the async device API described in the design
spec is a Phase 2 concern layered on top via `asyncio.to_thread`, and does
not require re-touching this phase's code. `transport/` only knows bytes
and BlueZ; `protocol/` only knows frame structure, never opens a socket
itself (it's handed a duck-typed object with `send(bytes)`/`recv(n,
timeout)`), which keeps it testable without hardware.

**Tech Stack:** Python 3.11+ (dev on 3.14.6 via `uv`), stdlib
`socket.AF_BLUETOOTH`/`BTPROTO_RFCOMM` for RFCOMM, a hand-rolled minimal
SDP client (Bluetooth Core Spec Vol 3 Part B — public standard, not
Sony-specific) for channel discovery, stdlib `argparse` for the CLI,
`pytest` for tests, `hatchling` as the build backend.

## Global Constraints

- Target device MAC for hardware tests/manual runs: `58:18:62:1F:C9:CB`.
- Sony vendor RFCOMM service UUID (from `bluetoothctl info`):
  `956c7b26-d49a-4ba8-b03f-b17d393cb6e2`.
- `requires-python = ">=3.11"` (per `README.md`).
- Library code (`transport/`, `protocol/`) never imports PyQt6 (per
  `CLAUDE.md` layer rule).
- `protocol/` stays free of socket I/O — pure byte transforms only, so it's
  unit-testable without hardware (per `CLAUDE.md`).
- Default `pytest` run excludes hardware tests; only `pytest -m hardware`
  runs them (per `CLAUDE.md` and design spec's testing strategy).
- The exact frame layout in Task 4 is a **hypothesis** carried over from
  community XM4/XM5 research, not confirmed for XM6. It must be flagged as
  such in code comments and `docs/protocol/`, and is expected to be
  corrected by a follow-up task once verified against the real device.
- Commit after every task using the repo's existing plain commit style (no
  `Co-Authored-By` trailer — already disabled globally).

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/sonus/__init__.py`
- Create: `src/sonus/transport/__init__.py`
- Create: `src/sonus/protocol/__init__.py`
- Create: `src/sonus/messages/__init__.py`
- Create: `src/sonus/device/__init__.py`
- Create: `src/sonus/cli/__init__.py`
- Create: `src/sonus/gui/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/hardware/__init__.py`
- Create: `tests/fixtures/captures/.gitkeep`
- Create: `.gitignore`
- Test: `tests/unit/test_package.py`

**Interfaces:**
- Produces: an installable `sonus` package importable as `import sonus`,
  a `uv`-managed virtualenv, and a working `pytest` command that later
  tasks' tests plug into.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "sonus"
version = "0.1.0"
description = "Linux driver and PyQt6 control app for the Sony WH-1000XM6"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
sonus = "sonus.cli.main:main"

[dependency-groups]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
markers = [
    "hardware: requires a connected WH-1000XM6 (run with -m hardware)",
]
addopts = "-m \"not hardware\""
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sonus"]
```

- [ ] **Step 2: Create package skeleton**

```bash
mkdir -p src/sonus/transport src/sonus/protocol src/sonus/messages src/sonus/device src/sonus/cli src/sonus/gui
mkdir -p tests/unit tests/hardware tests/fixtures/captures
touch src/sonus/__init__.py src/sonus/transport/__init__.py src/sonus/protocol/__init__.py \
      src/sonus/messages/__init__.py src/sonus/device/__init__.py src/sonus/cli/__init__.py \
      src/sonus/gui/__init__.py tests/__init__.py tests/unit/__init__.py tests/hardware/__init__.py \
      tests/fixtures/captures/.gitkeep
```

`src/sonus/__init__.py` content:

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Write `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
uv.lock
*.egg-info/
.pytest_cache/
.ruff_cache/
```

Note: we intentionally ignore `uv.lock` for a library project so consumers
resolve their own compatible versions; if the team later decides to pin,
remove this line and commit the lockfile.

- [ ] **Step 4: Write the smoke test**

```python
# tests/unit/test_package.py
import sonus


def test_package_has_version():
    assert sonus.__version__ == "0.1.0"
```

- [ ] **Step 5: Sync and run**

Run: `uv sync && uv run pytest -v`
Expected: 1 passed (`test_package_has_version`).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore src tests
git commit -m "chore: scaffold sonus package with uv and pytest"
```

---

### Task 2: SDP client for RFCOMM channel discovery

**Files:**
- Create: `src/sonus/transport/sdp.py`
- Test: `tests/unit/test_sdp.py`

**Interfaces:**
- Consumes: nothing from earlier tasks beyond the package skeleton.
- Produces:
  - `class SdpLookupError(Exception)`
  - `build_service_search_attribute_request(service_uuid: str, transaction_id: int = 0, max_attribute_bytes: int = 512) -> bytes`
  - `parse_rfcomm_channel(response: bytes) -> int` (raises `SdpLookupError` if no RFCOMM channel found in the response)
  - `find_rfcomm_channel(mac: str, service_uuid: str, timeout: float = 5.0) -> int` (opens a raw L2CAP socket to the SDP server PSM, hardware-touching)

This is a standard Bluetooth SDP (Service Discovery Protocol) client per
the public Bluetooth Core Specification (Vol 3, Part B) — not
Sony-specific, so no reverse-engineering concerns apply here.

- [ ] **Step 1: Write the failing test for request building and response parsing**

```python
# tests/unit/test_sdp.py
import pytest

from sonus.transport.sdp import (
    SdpLookupError,
    build_service_search_attribute_request,
    parse_rfcomm_channel,
)

SERVICE_UUID = "956c7b26-d49a-4ba8-b03f-b17d393cb6e2"


def test_build_request_starts_with_service_search_attribute_pdu_id():
    request = build_service_search_attribute_request(SERVICE_UUID, transaction_id=0x1234)
    # PDU ID 0x06 = SDP_ServiceSearchAttributeRequest
    assert request[0] == 0x06
    # Transaction ID is the next 2 bytes, big-endian
    assert request[1:3] == b"\x12\x34"


def test_build_request_embeds_the_128_bit_uuid_bytes():
    request = build_service_search_attribute_request(SERVICE_UUID)
    uuid_bytes = bytes.fromhex(SERVICE_UUID.replace("-", ""))
    assert uuid_bytes in request


def test_parse_rfcomm_channel_extracts_channel_from_protocol_descriptor_list():
    # Hand-built synthetic SDP_ServiceSearchAttributeResponse per the public
    # SDP byte layout: PDU header + attribute list containing a
    # ProtocolDescriptorList (attribute ID 0x0004) whose second protocol
    # entry is RFCOMM (UUID 0x0003) with a single uint8 channel parameter.
    #
    # DES(ProtocolDescriptorList) = [
    #   DES[ UUID(0x0100) L2CAP ],
    #   DES[ UUID(0x0003) RFCOMM, uint8 channel=8 ],
    # ]
    l2cap_proto = bytes([0x35, 0x03, 0x19, 0x01, 0x00])  # DES(3) { UUID16 0x0100 }
    rfcomm_proto = bytes([0x35, 0x05, 0x19, 0x00, 0x03, 0x08, 0x08])  # DES(5) { UUID16 0x0003, uint8 8 }
    protocol_descriptor_list = bytes([0x35, len(l2cap_proto) + len(rfcomm_proto)]) + l2cap_proto + rfcomm_proto

    attr_id = bytes([0x09, 0x00, 0x04])  # uint16 attribute ID 0x0004
    attribute_list = bytes([0x35, len(attr_id) + len(protocol_descriptor_list)]) + attr_id + protocol_descriptor_list

    # SDP_ServiceSearchAttributeResponse: PDU ID(1) + TxId(2) + ParamLen(2)
    # + AttributeListByteCount(2) + AttributeList + ContinuationState(1, 0=none)
    body = bytes([0x00, 0x00]) + len(attribute_list).to_bytes(2, "big") + attribute_list + bytes([0x00])
    response = bytes([0x07]) + bytes([0x12, 0x34]) + len(body).to_bytes(2, "big") + body

    assert parse_rfcomm_channel(response) == 8


def test_parse_rfcomm_channel_raises_when_rfcomm_not_present():
    l2cap_only = bytes([0x35, 0x03, 0x19, 0x01, 0x00])
    protocol_descriptor_list = bytes([0x35, len(l2cap_only)]) + l2cap_only
    attr_id = bytes([0x09, 0x00, 0x04])
    attribute_list = bytes([0x35, len(attr_id) + len(protocol_descriptor_list)]) + attr_id + protocol_descriptor_list
    body = bytes([0x00, 0x00]) + len(attribute_list).to_bytes(2, "big") + attribute_list + bytes([0x00])
    response = bytes([0x07]) + bytes([0x00, 0x00]) + len(body).to_bytes(2, "big") + body

    with pytest.raises(SdpLookupError):
        parse_rfcomm_channel(response)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_sdp.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sonus.transport.sdp'`

- [ ] **Step 3: Implement the SDP client**

```python
# src/sonus/transport/sdp.py
"""Minimal SDP (Service Discovery Protocol) client.

Implements just enough of the Bluetooth Core Specification (Vol 3, Part B)
to resolve an RFCOMM channel number for a given 128-bit service UUID on a
remote device. This is a public, standardized protocol — not specific to
any vendor's implementation.
"""
from __future__ import annotations

import socket

_PDU_SERVICE_SEARCH_ATTRIBUTE_REQUEST = 0x06
_PDU_SERVICE_SEARCH_ATTRIBUTE_RESPONSE = 0x07
_DES_UINT8_LEN = 0x35  # Data Element Sequence, 1-byte length follows
_UUID16_RFCOMM = 0x0003
_ATTR_PROTOCOL_DESCRIPTOR_LIST = 0x0004
_SDP_PSM = 0x0001


class SdpLookupError(Exception):
    """Raised when the SDP response does not contain an RFCOMM channel."""


def _encode_uuid128(service_uuid: str) -> bytes:
    return bytes.fromhex(service_uuid.replace("-", ""))


def build_service_search_attribute_request(
    service_uuid: str,
    transaction_id: int = 0,
    max_attribute_bytes: int = 512,
) -> bytes:
    uuid_bytes = _encode_uuid128(service_uuid)
    # ServiceSearchPattern: DES { UUID128 }
    service_search_pattern = bytes([0x1C]) + uuid_bytes  # 0x1C = UUID, 16-byte
    service_search_pattern = bytes([_DES_UINT8_LEN, len(service_search_pattern)]) + service_search_pattern

    # AttributeIDList: DES { uint16 attribute ID }
    attribute_id_list = bytes([0x09]) + _ATTR_PROTOCOL_DESCRIPTOR_LIST.to_bytes(2, "big")
    attribute_id_list = bytes([_DES_UINT8_LEN, len(attribute_id_list)]) + attribute_id_list

    params = (
        service_search_pattern
        + max_attribute_bytes.to_bytes(2, "big")
        + attribute_id_list
        + bytes([0x00])  # ContinuationState: none
    )

    return (
        bytes([_PDU_SERVICE_SEARCH_ATTRIBUTE_REQUEST])
        + transaction_id.to_bytes(2, "big")
        + len(params).to_bytes(2, "big")
        + params
    )


def _read_des_header(data: bytes, offset: int) -> tuple[int, int]:
    """Return (content_start_offset, content_length) for a DES at offset.

    Only supports the 1-byte-length DES encoding (type byte 0x35), which is
    all this client emits/expects.
    """
    if data[offset] != _DES_UINT8_LEN:
        raise SdpLookupError(f"expected DES (0x35) at offset {offset}, got {data[offset]:#x}")
    length = data[offset + 1]
    return offset + 2, length


def parse_rfcomm_channel(response: bytes) -> int:
    if not response or response[0] != _PDU_SERVICE_SEARCH_ATTRIBUTE_RESPONSE:
        raise SdpLookupError("not a ServiceSearchAttributeResponse")

    # Header: PDU ID(1) TxId(2) ParamLen(2) AttrListByteCount(2)
    body = response[5:]
    attr_list_byte_count = int.from_bytes(body[0:2], "big")
    attribute_list = body[2 : 2 + attr_list_byte_count]

    # attribute_list is DES { uint16 attrId, <value> }
    offset, _ = _read_des_header(attribute_list, 0)
    # uint16 attribute ID: type byte 0x09 + 2 bytes
    if attribute_list[offset] != 0x09:
        raise SdpLookupError("expected uint16 attribute ID")
    offset += 3

    # value is DES { protocol entries... }
    pdl_start, pdl_len = _read_des_header(attribute_list, offset)
    pdl = attribute_list[pdl_start : pdl_start + pdl_len]

    pos = 0
    while pos < len(pdl):
        entry_start, entry_len = _read_des_header(pdl, pos)
        entry = pdl[entry_start : entry_start + entry_len]
        pos = entry_start + entry_len

        # entry is UUID16(2 header bytes: 0x19 + 2-byte uuid) [+ uint8 param]
        if len(entry) >= 3 and entry[0] == 0x19:
            uuid16 = int.from_bytes(entry[1:3], "big")
            if uuid16 == _UUID16_RFCOMM and len(entry) >= 6 and entry[3] == 0x08:
                return entry[4]

    raise SdpLookupError("RFCOMM channel not found in ProtocolDescriptorList")


def find_rfcomm_channel(mac: str, service_uuid: str, timeout: float = 5.0) -> int:
    """Query the remote device's SDP server for the RFCOMM channel of service_uuid."""
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    sock.settimeout(timeout)
    try:
        sock.connect((mac, _SDP_PSM))
        sock.send(build_service_search_attribute_request(service_uuid))
        response = sock.recv(4096)
    finally:
        sock.close()
    return parse_rfcomm_channel(response)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_sdp.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sonus/transport/sdp.py tests/unit/test_sdp.py
git commit -m "feat: add minimal SDP client for RFCOMM channel discovery"
```

---

### Task 3: RFCOMM connection with retry/backoff

**Files:**
- Create: `src/sonus/transport/rfcomm.py`
- Test: `tests/unit/test_rfcomm.py`

**Interfaces:**
- Consumes: nothing from Task 2 directly (channel number is passed in by
  the caller — `cli/` wires SDP lookup + RFCOMM connect together later).
- Produces:
  - `class RfcommConnection` with `.send(data: bytes) -> None`,
    `.recv(bufsize: int = 4096, timeout: float | None = None) -> bytes`,
    `.close() -> None`, usable as a context manager.
  - `connect(mac: str, channel: int, timeout: float = 10.0) -> RfcommConnection`
  - `connect_with_backoff(connector: Callable[[], RfcommConnection], attempts: int = 3, base_delay: float = 1.0, sleep: Callable[[float], None] = time.sleep) -> RfcommConnection`
    (raises the last connector exception if all attempts fail)

- [ ] **Step 1: Write the failing test for backoff logic**

```python
# tests/unit/test_rfcomm.py
import pytest

from sonus.transport.rfcomm import connect_with_backoff


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_rfcomm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sonus.transport.rfcomm'`

- [ ] **Step 3: Implement RFCOMM connection and backoff**

```python
# src/sonus/transport/rfcomm.py
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
    sock.settimeout(timeout)
    sock.connect((mac, channel))
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_rfcomm.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sonus/transport/rfcomm.py tests/unit/test_rfcomm.py
git commit -m "feat: add RFCOMM connection wrapper with exponential backoff"
```

---

### Task 4: Frame codec (hypothesis, XM4/XM5-derived)

**Files:**
- Create: `src/sonus/protocol/framing.py`
- Test: `tests/unit/test_framing.py`
- Create: `docs/protocol/README.md`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `@dataclass(frozen=True) class Frame: seq: int; msg_type: int; payload: bytes`
  - `class FrameFormatError(Exception)`
  - `class FrameChecksumError(Exception)`
  - `encode_frame(seq: int, msg_type: int, payload: bytes) -> bytes`
  - `decode_frame(raw: bytes) -> Frame`

This layer implements the **hypothesis** frame structure from the design
spec: `START(0x3E) seq(1) msg_type(1) length(1, of payload) payload(N)
checksum(1) END(0x3C)`, with byte-stuffing: any raw occurrence of
`START`/`END`/`ESCAPE(0x3D)` inside `seq/msg_type/length/payload/checksum`
is replaced by `ESCAPE` followed by `(byte XOR 0x20)`. Checksum is the
two's-complement (256 minus sum, mod 256) of the unescaped
`seq+msg_type+length+payload` bytes. **This must be verified against the
real XM6 in Task 6's manual step and corrected in a follow-up task if
wrong** — do not treat this as confirmed.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_framing.py
import pytest

from sonus.protocol.framing import (
    Frame,
    FrameChecksumError,
    FrameFormatError,
    decode_frame,
    encode_frame,
)


def test_encode_decode_round_trip_no_escaping_needed():
    encoded = encode_frame(seq=1, msg_type=0x0C, payload=b"\x01\x02\x03")
    decoded = decode_frame(encoded)
    assert decoded == Frame(seq=1, msg_type=0x0C, payload=b"\x01\x02\x03")


def test_encode_starts_and_ends_with_markers():
    encoded = encode_frame(seq=0, msg_type=0x00, payload=b"")
    assert encoded[0] == 0x3E
    assert encoded[-1] == 0x3C


def test_encode_escapes_special_bytes_in_payload():
    # payload contains START, END, and ESCAPE bytes that must be stuffed
    encoded = encode_frame(seq=0, msg_type=0x01, payload=b"\x3e\x3c\x3d")
    # None of the special bytes should appear "bare" between the outer markers
    inner = encoded[1:-1]
    i = 0
    while i < len(inner):
        if inner[i] == 0x3D:
            i += 2  # escaped byte, skip both
            continue
        assert inner[i] not in (0x3E, 0x3C, 0x3D)
        i += 1


def test_decode_round_trips_escaped_payload():
    payload = b"\x3e\x3c\x3d\x00\xff"
    encoded = encode_frame(seq=5, msg_type=0x02, payload=payload)
    decoded = decode_frame(encoded)
    assert decoded == Frame(seq=5, msg_type=0x02, payload=payload)


def test_decode_raises_on_bad_checksum():
    encoded = bytearray(encode_frame(seq=1, msg_type=0x0C, payload=b"\x01"))
    encoded[-2] ^= 0xFF  # corrupt the checksum byte
    with pytest.raises(FrameChecksumError):
        decode_frame(bytes(encoded))


def test_decode_raises_on_missing_markers():
    with pytest.raises(FrameFormatError):
        decode_frame(b"\x01\x02\x03")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_framing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sonus.protocol.framing'`

- [ ] **Step 3: Implement the frame codec**

```python
# src/sonus/protocol/framing.py
"""Frame codec for the Sony proprietary RFCOMM protocol.

HYPOTHESIS, carried over from community XM4/XM5 reverse-engineering
research (not confirmed for the WH-1000XM6). Verify against the real
device before relying on this for anything beyond probing — see
docs/protocol/README.md.
"""
from __future__ import annotations

from dataclasses import dataclass

START = 0x3E
END = 0x3C
ESCAPE = 0x3D
_ESCAPE_XOR = 0x20
_SPECIAL_BYTES = (START, END, ESCAPE)


class FrameFormatError(Exception):
    """Raised when raw bytes don't form a well-shaped frame."""


class FrameChecksumError(Exception):
    """Raised when a decoded frame's checksum doesn't match its content."""


@dataclass(frozen=True)
class Frame:
    seq: int
    msg_type: int
    payload: bytes


def _checksum(data: bytes) -> int:
    return (0x100 - (sum(data) % 0x100)) % 0x100


def _stuff(data: bytes) -> bytes:
    out = bytearray()
    for byte in data:
        if byte in _SPECIAL_BYTES:
            out.append(ESCAPE)
            out.append(byte ^ _ESCAPE_XOR)
        else:
            out.append(byte)
    return bytes(out)


def _unstuff(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        if byte == ESCAPE:
            if i + 1 >= len(data):
                raise FrameFormatError("truncated escape sequence")
            out.append(data[i + 1] ^ _ESCAPE_XOR)
            i += 2
        else:
            out.append(byte)
            i += 1
    return bytes(out)


def encode_frame(seq: int, msg_type: int, payload: bytes) -> bytes:
    body = bytes([seq, msg_type, len(payload)]) + payload
    body += bytes([_checksum(body)])
    return bytes([START]) + _stuff(body) + bytes([END])


def decode_frame(raw: bytes) -> Frame:
    if len(raw) < 2 or raw[0] != START or raw[-1] != END:
        raise FrameFormatError("frame missing START/END markers")

    body = _unstuff(raw[1:-1])
    if len(body) < 4:
        raise FrameFormatError("frame body too short")

    seq, msg_type, length = body[0], body[1], body[2]
    payload = body[3 : 3 + length]
    if len(payload) != length:
        raise FrameFormatError("payload shorter than declared length")

    received_checksum = body[3 + length]
    expected_checksum = _checksum(body[: 3 + length])
    if received_checksum != expected_checksum:
        raise FrameChecksumError(
            f"checksum mismatch: expected {expected_checksum:#x}, got {received_checksum:#x}"
        )

    return Frame(seq=seq, msg_type=msg_type, payload=payload)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_framing.py -v`
Expected: 6 passed.

- [ ] **Step 5: Write the protocol documentation stub with legal notice**

```markdown
<!-- docs/protocol/README.md -->
# Protocol Notes

This directory records observations about the WH-1000XM6's RFCOMM control
protocol, gathered by sending bytes to and reading responses from a
user-owned device for interoperability purposes. It does not contain, and
must never contain, Sony's source code, firmware images, or disassembled
binaries — only descriptions of the observed data format (frame layout,
command IDs, payload shapes), which is fair-use reverse engineering for
interoperability (cf. the EU Software Directive Art. 6, DMCA §1201(f), and
the equivalent Korean Copyright Act §101-4).

## Frame structure (hypothesis, unverified on XM6)

Carried over from community XM4/XM5 research. See
`src/sonus/protocol/framing.py` for the implementation and
`docs/design/2026-08-15-sonus-driver-design.md` for the design
rationale. **Status: not yet confirmed against real XM6 traffic.**

| Field | Size | Notes |
|---|---|---|
| START | 1 byte | `0x3E` |
| seq | 1 byte | sequence number |
| msg_type | 1 byte | command/response type |
| length | 1 byte | payload length in bytes |
| payload | N bytes | command-specific |
| checksum | 1 byte | two's complement of seq+msg_type+length+payload, mod 256 |
| END | 1 byte | `0x3C` |

Byte stuffing: any occurrence of `0x3E`/`0x3C`/`0x3D` between START and END
is replaced with `0x3D` followed by `(byte XOR 0x20)`.

## Verification log

_(Append entries here as `sonus send`/`sonus sniff` sessions confirm or
correct the hypothesis above.)_
```

- [ ] **Step 6: Commit**

```bash
git add src/sonus/protocol/framing.py tests/unit/test_framing.py docs/protocol/README.md
git commit -m "feat: add hypothesis frame codec for the XM protocol"
```

---

### Task 5: ACK/sequencing session layer

**Files:**
- Create: `src/sonus/protocol/session.py`
- Test: `tests/unit/test_session.py`

**Interfaces:**
- Consumes: `Frame`, `encode_frame`, `decode_frame` from Task 4
  (`sonus.protocol.framing`).
- Produces:
  - `class ProtocolTimeoutError(Exception)`
  - `class ProtocolSession` with constructor
    `ProtocolSession(transport, timeout: float = 2.0, retries: int = 2)`
    where `transport` is any object with `.send(bytes) -> None` and
    `.recv(bufsize: int, timeout: float) -> bytes`.
  - `ProtocolSession.request(msg_type: int, payload: bytes = b"") -> Frame`
    — encodes and sends a frame with an auto-incrementing sequence number,
    waits for a response frame, retries on timeout up to `retries` times,
    raises `ProtocolTimeoutError` if all retries are exhausted.

- [ ] **Step 1: Write the failing tests using a fake transport**

```python
# tests/unit/test_session.py
import pytest

from sonus.protocol.framing import Frame, encode_frame
from sonus.protocol.session import ProtocolSession, ProtocolTimeoutError


class FakeTransport:
    """Records sent bytes; returns scripted responses or raises TimeoutError."""

    def __init__(self, responses):
        self.sent = []
        self._responses = list(responses)

    def send(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, bufsize: int, timeout: float) -> bytes:
        if not self._responses:
            raise TimeoutError("no more scripted responses")
        response = self._responses.pop(0)
        if response is None:
            raise TimeoutError("scripted timeout")
        return response


def test_request_sends_encoded_frame_with_seq_zero_first():
    transport = FakeTransport([encode_frame(seq=0, msg_type=0x01, payload=b"\xaa")])
    session = ProtocolSession(transport)

    session.request(msg_type=0x02, payload=b"\x01")

    assert len(transport.sent) == 1
    from sonus.protocol.framing import decode_frame

    sent_frame = decode_frame(transport.sent[0])
    assert sent_frame.seq == 0
    assert sent_frame.msg_type == 0x02
    assert sent_frame.payload == b"\x01"


def test_request_increments_sequence_across_calls():
    transport = FakeTransport(
        [
            encode_frame(seq=0, msg_type=0x01, payload=b""),
            encode_frame(seq=1, msg_type=0x01, payload=b""),
        ]
    )
    session = ProtocolSession(transport)

    session.request(msg_type=0x02)
    session.request(msg_type=0x02)

    from sonus.protocol.framing import decode_frame

    seqs = [decode_frame(sent).seq for sent in transport.sent]
    assert seqs == [0, 1]


def test_request_returns_decoded_response_frame():
    transport = FakeTransport([encode_frame(seq=0, msg_type=0x81, payload=b"\x99")])
    session = ProtocolSession(transport)

    response = session.request(msg_type=0x01)

    assert response == Frame(seq=0, msg_type=0x81, payload=b"\x99")


def test_request_retries_on_timeout_then_succeeds():
    transport = FakeTransport([None, encode_frame(seq=0, msg_type=0x81, payload=b"")])
    session = ProtocolSession(transport, retries=2)

    response = session.request(msg_type=0x01)

    assert response.msg_type == 0x81
    assert len(transport.sent) == 2  # resent once after the timeout


def test_request_raises_after_exhausting_retries():
    transport = FakeTransport([None, None])
    session = ProtocolSession(transport, retries=1)

    with pytest.raises(ProtocolTimeoutError):
        session.request(msg_type=0x01)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_session.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sonus.protocol.session'`

- [ ] **Step 3: Implement the session layer**

```python
# src/sonus/protocol/session.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_session.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sonus/protocol/session.py tests/unit/test_session.py
git commit -m "feat: add ACK/retry session layer over the frame codec"
```

---

### Task 6: `sonus` CLI — `probe`, `sniff`, `send`

**Files:**
- Create: `src/sonus/cli/main.py`
- Create: `src/sonus/cli/probe.py`
- Create: `src/sonus/cli/sniff.py`
- Create: `src/sonus/cli/send.py`
- Test: `tests/unit/test_cli_probe.py`
- Test: `tests/unit/test_cli_send.py`
- Test: `tests/unit/test_cli_sniff.py`

**Interfaces:**
- Consumes:
  - `sonus.transport.sdp.find_rfcomm_channel`
  - `sonus.transport.rfcomm.connect`, `sonus.transport.rfcomm.connect_with_backoff`, `sonus.transport.rfcomm.RfcommConnection`
  - `sonus.protocol.session.ProtocolSession`
- Produces:
  - `cli/probe.py: run_probe(mac: str, service_uuid: str, *, find_channel=find_rfcomm_channel, connect_fn=connect) -> str` (returns a human-readable summary; dependency-injected for testability)
  - `cli/sniff.py: run_sniff(mac: str, channel: int, out_path: str, *, connect_fn=connect, poll: Callable[[], bool] = lambda: True) -> int` (returns count of frames logged; `poll` lets tests stop the loop after one iteration)
  - `cli/send.py: run_send(mac: str, channel: int, msg_type: int, payload_hex: str, *, connect_fn=connect) -> str` (returns a human-readable summary of the response frame)
  - `cli/main.py: main(argv: list[str] | None = None) -> int` — argparse
    entry point wiring `probe`/`sniff`/`send` subcommands to the functions
    above.

- [ ] **Step 1: Write the failing test for `probe`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_probe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sonus.cli.probe'`

- [ ] **Step 3: Implement `cli/probe.py`**

```python
# src/sonus/cli/probe.py
from __future__ import annotations

from sonus.transport.rfcomm import connect as default_connect
from sonus.transport.sdp import find_rfcomm_channel as default_find_channel


def run_probe(
    mac: str,
    service_uuid: str,
    *,
    find_channel=default_find_channel,
    connect_fn=default_connect,
) -> str:
    channel = find_channel(mac, service_uuid)
    connection = connect_fn(mac, channel)
    try:
        return f"Found RFCOMM channel {channel} for {mac}; connected successfully."
    finally:
        connection.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_cli_probe.py -v`
Expected: 1 passed.

- [ ] **Step 5: Write the failing test for `send`**

```python
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
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_send.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sonus.cli.send'`

- [ ] **Step 7: Implement `cli/send.py`**

```python
# src/sonus/cli/send.py
from __future__ import annotations

from sonus.protocol.session import ProtocolSession
from sonus.transport.rfcomm import connect as default_connect


def run_send(
    mac: str,
    channel: int,
    *,
    msg_type: int,
    payload_hex: str,
    connect_fn=default_connect,
) -> str:
    connection = connect_fn(mac, channel)
    try:
        session = ProtocolSession(connection)
        payload = bytes.fromhex(payload_hex)
        response = session.request(msg_type=msg_type, payload=payload)
        return (
            f"Response: msg_type={response.msg_type:#04x} "
            f"seq={response.seq} payload={response.payload.hex()}"
        )
    finally:
        connection.close()
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_cli_send.py -v`
Expected: 1 passed.

- [ ] **Step 9: Write the failing test for `sniff`**

```python
# tests/unit/test_cli_sniff.py
import json

from sonus.cli.sniff import run_sniff


class _FakeConnection:
    def __init__(self, frames):
        self._frames = list(frames)

    def recv(self, bufsize: int, timeout: float) -> bytes:
        if not self._frames:
            raise TimeoutError("no more data")
        return self._frames.pop(0)

    def close(self) -> None:
        pass


def test_run_sniff_logs_received_frames_as_jsonl(tmp_path):
    out_path = tmp_path / "capture.jsonl"
    connection = _FakeConnection([b"\x01\x02", b"\x03\x04"])
    call_count = {"n": 0}

    def poll():
        call_count["n"] += 1
        return call_count["n"] <= 2  # stop after 2 iterations

    logged = run_sniff(
        "58:18:62:1F:C9:CB",
        8,
        str(out_path),
        connect_fn=lambda mac, channel, timeout=10.0: connection,
        poll=poll,
    )

    assert logged == 2
    lines = out_path.read_text().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["direction"] == "rx"
    assert first["hex"] == "0102"
    assert "ts" in first
```

- [ ] **Step 10: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_sniff.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sonus.cli.sniff'`

- [ ] **Step 11: Implement `cli/sniff.py`**

```python
# src/sonus/cli/sniff.py
from __future__ import annotations

import json
import time
from collections.abc import Callable

from sonus.transport.rfcomm import connect as default_connect


def run_sniff(
    mac: str,
    channel: int,
    out_path: str,
    *,
    connect_fn=default_connect,
    poll: Callable[[], bool] = lambda: True,
) -> int:
    connection = connect_fn(mac, channel)
    logged = 0
    try:
        with open(out_path, "a") as out_file:
            while poll():
                try:
                    data = connection.recv(bufsize=4096, timeout=1.0)
                except TimeoutError:
                    continue
                record = {"ts": time.time(), "direction": "rx", "hex": data.hex()}
                out_file.write(json.dumps(record) + "\n")
                out_file.flush()
                logged += 1
    finally:
        connection.close()
    return logged
```

- [ ] **Step 12: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_cli_sniff.py -v`
Expected: 1 passed.

- [ ] **Step 13: `cli/main.py`에 명령 연결**

```python
# src/sonus/cli/main.py
from __future__ import annotations

import argparse
import sys

from sonus.cli.probe import run_probe
from sonus.cli.send import run_send
from sonus.cli.sniff import run_sniff

DEFAULT_SERVICE_UUID = "956c7b26-d49a-4ba8-b03f-b17d393cb6e2"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sonus")
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser("probe", help="discover the RFCOMM channel and connect")
    probe_parser.add_argument("--mac", required=True)
    probe_parser.add_argument("--service-uuid", default=DEFAULT_SERVICE_UUID)

    sniff_parser = subparsers.add_parser("sniff", help="log raw received bytes to a file")
    sniff_parser.add_argument("--mac", required=True)
    sniff_parser.add_argument("--channel", type=int, required=True)
    sniff_parser.add_argument("--out", required=True)

    send_parser = subparsers.add_parser("send", help="send a raw frame and print the response")
    send_parser.add_argument("--mac", required=True)
    send_parser.add_argument("--channel", type=int, required=True)
    send_parser.add_argument("--type", type=lambda s: int(s, 0), required=True, dest="msg_type")
    send_parser.add_argument("--payload", default="", help="hex-encoded payload bytes")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

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
        print(run_send(args.mac, args.channel, msg_type=args.msg_type, payload_hex=args.payload))

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 14: Run the full unit suite**

Run: `uv run pytest -v`
Expected: all tests pass (Tasks 1-6's unit tests), hardware tests skipped
by default.

- [ ] **Step 15: Commit**

```bash
git add src/sonus/cli tests/unit/test_cli_probe.py tests/unit/test_cli_send.py tests/unit/test_cli_sniff.py
git commit -m "feat: add sonus CLI with probe, sniff, and send subcommands"
```

- [ ] **Step 16 (manual, not automated): Verify against the real device**

This step is run interactively by the user/developer against the actual
headset (`58:18:62:1F:C9:CB`) — it is exploratory and cannot be scripted
in advance, since its purpose is to discover whether Task 4's hypothesis
frame structure is correct.

```bash
uv run sonus probe --mac 58:18:62:1F:C9:CB
uv run sonus sniff --mac 58:18:62:1F:C9:CB --channel <channel-from-probe> --out /tmp/xm6-capture.jsonl
# In another terminal or by pressing a button on the headset, trigger some
# activity (power on/off, ANC button, volume change) and watch the capture
# file grow.
uv run sonus send --mac 58:18:62:1F:C9:CB --channel <channel> --type 0x01 --payload ""
```

Record findings — whether frames decode cleanly, what msg_types appear,
any corrections to the hypothesis — in `docs/protocol/README.md` under
"Verification log", and open a follow-up task/plan for Phase 1.5 (frame
structure corrections) if the hypothesis doesn't hold.

---

## Self-Review Notes

- **Spec coverage:** L1 transport (Task 3 + SDP in Task 2), L2 protocol
  (Task 4 framing + Task 5 session), CLI probe/sniff/send (Task 6) are all
  covered. Messages registry (L3), device API (L4), and GUI are
  deliberately **out of scope** for this plan — they depend on Task 6's
  manual verification step producing a confirmed (or corrected) frame
  structure and a first real command, and are covered by the Phase 2 plan
  written after that verification happens.
- **No placeholders:** every step has runnable code; the one manual step
  (Task 6 Step 16) is explicitly hardware-interactive by nature, not a
  deferred implementation detail.
- **Type consistency:** `Frame`, `encode_frame`, `decode_frame` signatures
  introduced in Task 4 are used identically in Task 5 and by `cli/send.py`
  in Task 6. `RfcommConnection`'s `.send`/`.recv`/`.close` interface
  introduced in Task 3 matches what `ProtocolSession` (Task 5) and the CLI
  modules (Task 6) expect via duck typing.
