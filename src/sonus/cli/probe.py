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
                frame.data_type == DATA_TYPE_MDR and frame.payload.startswith(b"\x01")
            ),
        )
        return (
            f"Found RFCOMM channel {channel} for {mac}; "
            f"protocol_info={response.payload.hex()}"
        )
    finally:
        connection.close()
