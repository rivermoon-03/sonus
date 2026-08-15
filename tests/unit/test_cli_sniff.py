# tests/unit/test_cli_sniff.py
import json

import pytest

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


class _EofConnection:
    def __init__(self):
        self.recv_calls = 0
        self.closed = False

    def recv(self, bufsize: int, timeout: float) -> bytes:
        self.recv_calls += 1
        if self.recv_calls > 1:
            raise AssertionError("recv called after RFCOMM EOF")
        return b""

    def close(self) -> None:
        self.closed = True


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


def test_run_sniff_replaces_an_existing_capture(tmp_path):
    out_path = tmp_path / "capture.jsonl"
    out_path.write_text('{"stale": true}\n')
    connection = _FakeConnection([b"\xaa"])
    calls = 0

    def poll():
        nonlocal calls
        calls += 1
        return calls == 1

    run_sniff(
        "58:18:62:1F:C9:CB",
        9,
        str(out_path),
        connect_fn=lambda mac, channel, timeout=10.0: connection,
        poll=poll,
    )

    records = [json.loads(line) for line in out_path.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["hex"] == "aa"


def test_run_sniff_raises_on_rfcomm_eof_and_closes_connection(tmp_path):
    out_path = tmp_path / "capture.jsonl"
    connection = _EofConnection()

    with pytest.raises(ConnectionError, match="RFCOMM connection closed"):
        run_sniff(
            "58:18:62:1F:C9:CB",
            9,
            str(out_path),
            connect_fn=lambda mac, channel, timeout=10.0: connection,
        )

    assert connection.closed is True
