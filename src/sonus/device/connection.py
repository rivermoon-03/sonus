from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from sonus.device.xm6 import SonyXm6Device
from sonus.messages.registry import FEATURES
from sonus.messages.types import FeatureSpec
from sonus.protocol.session import ProtocolSession
from sonus.transport.rfcomm import connect_with_retries as default_connect
from sonus.transport.sdp import find_rfcomm_channel as default_find_channel

DEFAULT_SERVICE_UUID = "956c7b26-d49a-4ba8-b03f-b17d393cb6e2"


@contextmanager
def open_xm6_device(
    mac: str,
    channel: int | None = None,
    *,
    features: Mapping[str, FeatureSpec] = FEATURES,
    find_channel=default_find_channel,
    connect_fn=default_connect,
) -> Iterator[SonyXm6Device]:
    resolved_channel = channel
    if resolved_channel is None:
        resolved_channel = find_channel(mac, DEFAULT_SERVICE_UUID)
    connection = connect_fn(mac, resolved_channel)
    try:
        yield SonyXm6Device(ProtocolSession(connection), features=features)
    finally:
        connection.close()
