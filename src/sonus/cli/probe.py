# src/sonus/cli/probe.py
from __future__ import annotations

from sonus.transport.rfcomm import connect_with_retries as default_connect
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
