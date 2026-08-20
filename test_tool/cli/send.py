# test_tool/cli/send.py
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
