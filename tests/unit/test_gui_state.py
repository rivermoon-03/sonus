from __future__ import annotations

from sonus.device.xm6 import FeatureResult
from sonus.gui.state import GUI_FEATURE_KEYS, friendly_error, serialize_result
from sonus.protocol.session import ProtocolTimeoutError
from sonus.transport.sdp import SdpLookupError


def test_gui_feature_list_excludes_known_slow_le_audio_queries():
    assert "battery" in GUI_FEATURE_KEYS
    assert "equalizer" in GUI_FEATURE_KEYS
    assert "le_audio_status" not in GUI_FEATURE_KEYS
    assert "le_audio_compatibility" not in GUI_FEATURE_KEYS


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
