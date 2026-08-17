import pytest

from sonus.messages.codec import (
    DecodeError,
    decode_auto_power_off,
    decode_battery,
    decode_bool,
    decode_noise_control,
    decode_speak_to_chat,
    decode_string,
    encode_auto_power_off,
    encode_connection_mode,
    encode_dsee,
    encode_equalizer,
    encode_noise_control,
    encode_safe_listening,
    encode_safe_volume,
    encode_speak_to_chat,
    encode_system_toggle,
    encode_voice_guidance,
    encode_voice_guidance_volume,
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
    assert FEATURES["speak_to_chat"].decode(bytes.fromhex("f70c0101")) == {
        "enabled": False,
        "preview": False,
    }
    assert FEATURES["safe_listening"].decode(bytes.fromhex("570200")) is True


def test_registry_gives_names_to_common_xm6_values():
    assert FEATURES["codec"].decode(bytes.fromhex("130210")) == "LDAC"
    assert FEATURES["connection_mode"].decode(bytes.fromhex("e70000")) == "sound_quality"
    assert FEATURES["auto_power_off"].decode(bytes.fromhex("27051100")) == {
        "mode": "disabled",
        "last_mode": "5_minutes",
    }
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


def test_noise_control_preserves_every_wire_field():
    assert decode_noise_control(bytes.fromhex("671901000000100000")) == {
        "enabled": False,
        "mode": "noise_cancelling",
        "focus_voice": False,
        "ambient_level": 16,
        "auto_ambient": False,
        "adaptive_sensitivity": 0,
    }


def test_auto_power_off_preserves_last_selected_value():
    assert decode_auto_power_off(bytes.fromhex("27051100")) == {
        "mode": "disabled",
        "last_mode": "5_minutes",
    }


def test_speak_to_chat_preserves_preview_mode():
    assert decode_speak_to_chat(bytes.fromhex("f70c0101")) == {
        "enabled": False,
        "preview": False,
    }


def test_encode_candidate_write_payloads_exactly():
    assert encode_noise_control(
        {
            "enabled": True,
            "mode": "ambient_sound",
            "focus_voice": False,
            "ambient_level": 15,
            "auto_ambient": False,
            "adaptive_sensitivity": 0,
        }
    ) == bytes.fromhex("6819010101000f0000")
    assert encode_equalizer(
        {"preset": 0xA1, "bands": [8, 9, 7, 5, 7, 7, 7, 6, 10, 11]}
    ) == bytes.fromhex("5800a10a08090705070707060a0b")
    assert encode_connection_mode("stable_connection") == bytes.fromhex("e80001")
    assert encode_system_toggle(0x01, False) == bytes.fromhex("f80101")
    assert encode_speak_to_chat({"enabled": True, "preview": False}) == bytes.fromhex(
        "f80c0001"
    )
    assert encode_auto_power_off(
        {"mode": "180_minutes", "last_mode": "180_minutes"}
    ) == bytes.fromhex("28050303")
    assert encode_voice_guidance(
        {"enabled": False, "language": "japanese"}
    ) == bytes.fromhex("4801010b")
    assert encode_voice_guidance_volume(-1) == bytes.fromhex("4820ff01")
    assert encode_safe_listening(
        {"enabled": False, "preview": False}
    ) == bytes.fromhex("58020101")
    assert encode_safe_volume({"limited": False, "enabled": False}) == bytes.fromhex(
        "58040101"
    )


@pytest.mark.parametrize(
    ("encoder", "value"),
    [
        (encode_noise_control, {"enabled": True}),
        (encode_equalizer, {"preset": 0xA1, "bands": [10] * 9}),
        (encode_connection_mode, "unknown"),
        (encode_voice_guidance_volume, 3),
    ],
)
def test_write_encoders_reject_incomplete_or_out_of_range_values(encoder, value):
    with pytest.raises((TypeError, ValueError)):
        encoder(value)


@pytest.mark.parametrize(
    ("key", "notification"),
        [
            ("auto_pause", "f90101"),
        ("speak_to_chat", "f90c0001"),
        ("auto_power_off", "29050303"),
            ("voice_guidance_volume", "4920ff"),
    ],
)
def test_candidate_registry_entries_match_their_write_notifications(key, notification):
    feature = FEATURES[key]

    assert feature.writable is True
    assert feature.matches_write_payload(bytes.fromhex(notification))


def test_safe_listening_availability_queries_are_not_claimed_as_writable_settings():
    assert FEATURES["noise_control"].writable is False
    assert FEATURES["safe_listening"].writable is False
    assert FEATURES["safe_volume"].writable is False


def test_equalizer_write_is_ack_only_and_verified_by_a_followup_get():
    feature = FEATURES["equalizer"]

    assert feature.writable is True
    assert feature.write_response_command is None
    assert feature.write_response_type is None


def test_connection_mode_write_is_ack_only_and_verified_by_a_followup_get():
    feature = FEATURES["connection_mode"]

    assert feature.write_response_command is None
    assert feature.write_response_type is None


def test_voice_guidance_write_is_verified_by_full_followup_get():
    feature = FEATURES["voice_guidance"]

    assert feature.write_response_command is None
    assert feature.write_response_type is None
