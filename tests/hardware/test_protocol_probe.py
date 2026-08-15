import pytest

from sonus.cli.main import DEFAULT_SERVICE_UUID
from sonus.cli.probe import run_probe

XM6_MAC = "58:18:62:1F:C9:CB"


@pytest.mark.hardware
def test_xm6_protocol_info_probe():
    result = run_probe(XM6_MAC, DEFAULT_SERVICE_UUID)

    assert "channel 9" in result
    assert "protocol_info=0100030030320000" in result
