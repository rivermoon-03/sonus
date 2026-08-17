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
        "error": result.error,
    }


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
