import pytest

from sonus.messages.codec import (
    DecodeError,
    decode_battery,
    decode_bool,
    decode_string,
    encode_dsee,
    decode_wearing_status,
)
from sonus.messages.registry import FEATURES, parse_support_functions
from sonus.messages.types import Safety


def test_decode_prefixed_device_string_from_xm6_capture():
    assert decode_string(bytes.fromhex("05010a57482d31303030584d36"), 0x05, 0x01) == "WH-1000XM6"


def test_decode_battery_from_xm6_capture():
    assert decode_battery(bytes.fromhex("23005300"), 0x23, 0x00) == {
        "level": 83,
        "charging": False,
    }


@pytest.mark.parametrize(
    ("payload", "expected"),
    [("e70100", False), ("e70101", True), ("f70100", False)],
)
def test_decode_boolean_setting(payload, expected):
    raw = bytes.fromhex(payload)
    assert decode_bool(raw, raw[0], raw[1]) is expected


def test_decode_rejects_wrong_response_identity():
    with pytest.raises(DecodeError, match="expected"):
        decode_battery(bytes.fromhex("130210"), 0x23, 0x00)


def test_parse_support_function_pairs_from_xm6_capture():
    payload = bytes.fromhex(
        "07000410ff20ff57136d0b"
    )

    assert parse_support_functions(payload) == {
        0x10: 0xFF,
        0x20: 0xFF,
        0x57: 0x13,
        0x6D: 0x0B,
    }


def test_registry_contains_only_read_or_reversible_actions():
    assert FEATURES
    assert {feature.safety for feature in FEATURES.values()} <= {
        Safety.READ_ONLY,
        Safety.REVERSIBLE,
        Safety.EXPERIMENTAL_READ,
    }
    assert not {"power_off", "factory_reset", "firmware_update"} & FEATURES.keys()


def test_every_response_matcher_rejects_unrelated_notification():
    notification = bytes.fromhex("c90100096f7043686b4261747400")

    assert all(not feature.matches_payload(notification) for feature in FEATURES.values())


@pytest.mark.parametrize(("value", "expected"), [(False, "e80100"), (True, "e80101")])
def test_encode_verified_dsee_setting(value, expected):
    assert encode_dsee(value).hex() == expected


def test_dsee_registry_accepts_write_notification_identity():
    assert FEATURES["dsee"].matches_write_payload(bytes.fromhex("e90101"))


def test_table2_feature_uses_second_data_type_and_exact_matcher():
    feature = FEATURES["safe_listening"]

    assert feature.data_type == 0x0E
    assert feature.matches_payload(bytes.fromhex("570200"))
    assert not feature.matches_payload(bytes.fromhex("570400"))


def test_decode_xm6_not_worn_status():
    assert decode_wearing_status(bytes.fromhex("f30004")) == "not_worn"


def test_registry_decodes_sony_on_off_values_without_inverting_them():
    assert FEATURES["auto_pause"].decode(bytes.fromhex("f70100")) is True
    assert FEATURES["speak_to_chat"].decode(bytes.fromhex("f70c0101")) is False
    assert FEATURES["safe_listening"].decode(bytes.fromhex("570200")) is True


def test_registry_gives_names_to_common_xm6_values():
    assert FEATURES["codec"].decode(bytes.fromhex("130210")) == "LDAC"
    assert FEATURES["connection_mode"].decode(bytes.fromhex("e70000")) == "sound_quality"
    assert FEATURES["auto_power_off"].decode(bytes.fromhex("27051100")) == "disabled"
    assert FEATURES["voice_guidance"].decode(bytes.fromhex("4701000b")) == {
        "enabled": True,
        "language": "japanese",
    }


def test_decode_xm6_protocol_info_fields():
    assert FEATURES["protocol"].decode(bytes.fromhex("0100030030320000")) == {
        "version": "02",
        "version_raw": "03003032",
        "table1": True,
        "table2": True,
    }
