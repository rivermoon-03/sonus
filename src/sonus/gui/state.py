from __future__ import annotations

from typing import Any

from sonus.device.xm6 import FeatureResult
from sonus.protocol.session import ProtocolTimeoutError
from sonus.transport.sdp import SdpLookupError

GUI_FEATURE_KEYS = (
    "model_name",
    "firmware_version",
    "battery",
    "codec",
    "connection_mode",
    "noise_control",
    "equalizer",
    "dsee",
    "auto_pause",
    "speak_to_chat",
    "auto_power_off",
    "voice_guidance",
    "voice_guidance_volume",
    "wearing_status",
    "safe_listening",
    "safe_volume",
)

# 연결되어 있는 동안 항상 짧은 주기로 재조회하는 항목. 착용 감지처럼 실기기에서는
# 즉시 바뀌지만 수동 새로고침 전까지는 화면에 반영되지 않던 지연을 줄인다.
QUICK_FEATURE_KEYS = (
    "wearing_status",
    "battery",
)

# 디버그 패널 전용 실시간 조회 항목. 상태 새로고침(GUI_FEATURE_KEYS)에는 포함하지
# 않고, 디버그 패널이 열려 있을 때만 별도로 폴링한다 — 대부분 미해독 원시 바이트라
# 매 새로고침마다 가져올 필요가 없다.
DEBUG_FEATURE_KEYS = (
    "battery",
    "wearing_status",
    "noise_control",
    "protocol",
    "support_functions",
    "table2_support_functions",
    "call_mic_control",
    "headset_auto_switch",
    "le_audio_status",
    "le_audio_compatibility",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def serialize_result(result: FeatureResult) -> dict[str, object]:
    return {
        "key": result.key,
        "label": result.label,
        "value": _json_value(result.value),
        "supported": result.supported,
        "writable": result.writable,
        "raw": result.raw,
        "error": result.error,
    }


_CONNECTION_LABELS = {"connected": "연결됨", "connecting": "연결 중", "failed": "연결 실패"}


def connection_status_label(state: str | None) -> str:
    return _CONNECTION_LABELS.get(state, "연결 대기")


def battery_status_label(feature_payload: dict[str, object]) -> str | None:
    """트레이 표시용 배터리 문구. 배터리 항목이 아니거나 값이 없으면 None."""
    if feature_payload.get("key") != "battery" or not feature_payload.get("supported", True):
        return None
    value = feature_payload.get("value")
    if not isinstance(value, dict) or "level" not in value:
        return None
    charging = " · 충전 중" if value.get("charging") else ""
    return f"배터리 {value['level']}%{charging}"


def friendly_error(error: Exception) -> str:
    if isinstance(error, SdpLookupError):
        return "헤드셋을 찾지 못했습니다."
    if isinstance(error, (ProtocolTimeoutError, TimeoutError)):
        return "기기 응답이 없습니다."
    return "Bluetooth 연결에 실패했습니다."


def feature_error_code(error: Exception) -> str:
    if isinstance(error, (ProtocolTimeoutError, TimeoutError)):
        return "timeout"
    if isinstance(error, ConnectionError):
        return "connection_closed"
    return error.__class__.__name__.removesuffix("Error").lower()
