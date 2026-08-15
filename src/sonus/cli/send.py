# src/sonus/cli/send.py
from __future__ import annotations

from sonus.protocol.session import ProtocolSession
from sonus.transport.rfcomm import connect_with_retries as default_connect


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
