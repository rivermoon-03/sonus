# test_tool/cli/sniff.py
from __future__ import annotations

import json
import time
from collections.abc import Callable

from sonus.transport.rfcomm import connect_with_retries as default_connect


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
        with open(out_path, "w") as out_file:
            while poll():
                try:
                    data = connection.recv(bufsize=4096, timeout=1.0)
                except TimeoutError:
                    continue
                if data == b"":
                    raise ConnectionError("RFCOMM connection closed")
                record = {"ts": time.time(), "direction": "rx", "hex": data.hex()}
                out_file.write(json.dumps(record) + "\n")
                out_file.flush()
                logged += 1
    finally:
        connection.close()
    return logged
