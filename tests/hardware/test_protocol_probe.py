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


def _alternate_value(key, original):
    if key in {"dsee", "auto_pause"}:
        return not original
    if key == "noise_control":
        # Only ambient_level/mode are proven verifiable (2026-08-17, worn). Do not
        # toggle "enabled" here -- its GET value is tied to wearing state, not a
        # stored preference, so it cannot be write-verified (see registry.py).
        level = original["ambient_level"]
        return {**original, "ambient_level": level - 2 if level >= 3 else level + 2}
    if key == "equalizer":
        bands = list(original["bands"])
        bands[0] = bands[0] + 1 if bands[0] < 20 else bands[0] - 1
        return {**original, "bands": bands}
    if key == "speak_to_chat":
        return {**original, "enabled": not original["enabled"]}
    if key == "connection_mode":
        return (
            "stable_connection"
            if original == "sound_quality"
            else "sound_quality"
        )
    if key == "auto_power_off":
        return {
            "mode": "when_removed" if original["mode"] == "disabled" else "disabled",
            "last_mode": original["last_mode"],
        }
    if key == "voice_guidance":
        return {**original, "enabled": not original["enabled"]}
    if key == "voice_guidance_volume":
        return original + 1 if original < 2 else original - 1
    raise AssertionError(f"no safe alternate for {key}")


@pytest.mark.hardware
@pytest.mark.parametrize(
    "key",
    [
        "dsee",
        "equalizer",
        "auto_pause",
        "speak_to_chat",
        "connection_mode",
        "auto_power_off",
        "voice_guidance",
        "voice_guidance_volume",
        "noise_control",
    ],
)
def test_xm6_verified_write_is_restored(key):
    # noise_control specifically requires the headset to be worn for the whole
    # duration of this test -- taking it off mid-test changes what GET reports
    # and will fail the restore-comparison (not a protocol bug, see registry.py).
    channel = find_rfcomm_channel(XM6_MAC, DEFAULT_SERVICE_UUID)
    connection = connect_with_retries(XM6_MAC, channel)
    try:
        device = SonyXm6Device(ProtocolSession(connection))
        original = device.get(key)
        alternate = _alternate_value(key, original.value)

        with device.temporary_setting(key, alternate) as changed:
            assert changed.value == alternate

        restored = device.get(key)
        assert restored.value == original.value
    finally:
        connection.close()
