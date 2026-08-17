import pytest

from sonus.cli.main import DEFAULT_SERVICE_UUID
from sonus.cli.probe import run_probe
from sonus.device import SonyXm6Device
from sonus.protocol.session import ProtocolSession
from sonus.transport.rfcomm import connect_with_retries
from sonus.transport.sdp import find_rfcomm_channel

XM6_MAC = "58:18:62:1F:C9:CB"


@pytest.mark.hardware
def test_xm6_protocol_info_probe():
    result = run_probe(XM6_MAC, DEFAULT_SERVICE_UUID)

    assert "channel 9" in result
    assert "protocol_info=0100030030320000" in result


@pytest.mark.hardware
def test_xm6_dsee_temporary_setting_is_restored():
    channel = find_rfcomm_channel(XM6_MAC, DEFAULT_SERVICE_UUID)
    connection = connect_with_retries(XM6_MAC, channel)
    try:
        device = SonyXm6Device(ProtocolSession(connection))
        original = device.get("dsee").value

        with device.temporary_setting("dsee", not original) as changed:
            assert changed.value is not original

        assert device.get("dsee").value is original
    finally:
        connection.close()
