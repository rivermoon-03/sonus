from __future__ import annotations

from sonus.device.xm6 import FeatureResult
from sonus.gui.state import (
    DEBUG_FEATURE_KEYS,
    GUI_FEATURE_KEYS,
    battery_status_label,
    connection_status_label,
    friendly_error,
    serialize_result,
)
from sonus.protocol.session import ProtocolTimeoutError
from sonus.transport.sdp import SdpLookupError


def test_gui_feature_list_excludes_known_slow_le_audio_queries():
    assert "battery" in GUI_FEATURE_KEYS
    assert "equalizer" in GUI_FEATURE_KEYS
    assert "le_audio_status" not in GUI_FEATURE_KEYS
    assert "le_audio_compatibility" not in GUI_FEATURE_KEYS


def test_debug_feature_list_covers_raw_and_sensor_telemetry():
    assert "le_audio_status" in DEBUG_FEATURE_KEYS
    assert "le_audio_compatibility" in DEBUG_FEATURE_KEYS
    assert "call_mic_control" in DEBUG_FEATURE_KEYS
    assert "wearing_status" in DEBUG_FEATURE_KEYS
    assert "battery" in DEBUG_FEATURE_KEYS


def test_serialize_result_preserves_verified_writable_state_and_nested_value():
    result = FeatureResult(
        "battery",
        "배터리",
        {"level": 67, "charging": False},
        writable=True,
        raw="23004300",
    )

    assert serialize_result(result) == {
        "key": "battery",
        "label": "배터리",
        "value": {"level": 67, "charging": False},
        "supported": True,
        "writable": True,
        "raw": "23004300",
        "error": None,
    }


def test_serialize_unsupported_result_keeps_item_level_error():
    result = FeatureResult("codec", "코덱", supported=False, error="timeout")

    assert serialize_result(result)["error"] == "timeout"
    assert serialize_result(result)["supported"] is False


def test_friendly_error_hides_internal_details():
    assert friendly_error(SdpLookupError("raw SDP")) == "헤드셋을 찾지 못했습니다."
    assert friendly_error(ProtocolTimeoutError("packet bytes")) == "기기 응답이 없습니다."
    assert friendly_error(OSError("socket detail")) == "Bluetooth 연결에 실패했습니다."


def test_connection_status_label_covers_known_and_unknown_states():
    assert connection_status_label("connected") == "연결됨"
    assert connection_status_label("connecting") == "연결 중"
    assert connection_status_label("failed") == "연결 실패"
    assert connection_status_label(None) == "연결 대기"
    assert connection_status_label("bogus") == "연결 대기"


def test_battery_status_label_formats_level_and_charging():
    assert (
        battery_status_label({"key": "battery", "value": {"level": 82, "charging": True}})
        == "배터리 82% · 충전 중"
    )
    assert (
        battery_status_label({"key": "battery", "value": {"level": 40, "charging": False}})
        == "배터리 40%"
    )


def test_battery_status_label_ignores_non_battery_or_unsupported_payloads():
    assert battery_status_label({"key": "codec", "value": "LDAC"}) is None
    assert battery_status_label({"key": "battery", "supported": False}) is None
    assert battery_status_label({"key": "battery", "value": None}) is None
