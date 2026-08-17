from __future__ import annotations

from functools import partial

from sonus.messages.codec import (
    DecodeError,
    decode_battery,
    decode_auto_power_off,
    decode_bool,
    decode_byte,
    decode_bytes,
    decode_codec,
    decode_connection_mode,
    decode_equalizer,
    decode_noise_control,
    decode_protocol,
    decode_string,
    decode_signed_byte,
    decode_sony_on_off,
    decode_speak_to_chat,
    decode_voice_guidance,
    decode_wearing_status,
    encode_dsee,
)
from sonus.messages.types import FeatureSpec, Safety
from sonus.protocol.framing import DATA_TYPE_MDR_NO2


def parse_support_functions(payload: bytes) -> dict[int, int]:
    if len(payload) < 3 or payload[:2] != b"\x07\x00":
        raise DecodeError("expected support-function response 0700")
    count = payload[2]
    body = payload[3:]
    if len(body) != count * 2:
        raise DecodeError(f"support list declares {count} entries")
    return {body[index]: body[index + 1] for index in range(0, len(body), 2)}


FEATURES: dict[str, FeatureSpec] = {
    feature.key: feature
    for feature in (
        FeatureSpec("protocol", "프로토콜", b"\x00\x00", 0x01, 0x00, decode_protocol),
        FeatureSpec(
            "support_functions",
            "지원 기능",
            b"\x06\x00",
            0x07,
            0x00,
            parse_support_functions,
        ),
        FeatureSpec(
            "table2_support_functions",
            "추가 지원 기능",
            b"\x06\x00",
            0x07,
            0x00,
            parse_support_functions,
            data_type=DATA_TYPE_MDR_NO2,
        ),
        FeatureSpec(
            "model_name",
            "모델명",
            b"\x04\x01",
            0x05,
            0x01,
            partial(decode_string, command=0x05, item_type=0x01),
        ),
        FeatureSpec(
            "firmware_version",
            "펌웨어 버전",
            b"\x04\x02",
            0x05,
            0x02,
            partial(decode_string, command=0x05, item_type=0x02),
        ),
        FeatureSpec(
            "battery",
            "배터리",
            b"\x22\x00",
            0x23,
            0x00,
            partial(decode_battery, command=0x23, item_type=0x00),
            function_id=0x20,
        ),
        FeatureSpec(
            "codec",
            "오디오 코덱",
            b"\x12\x02",
            0x13,
            0x02,
            decode_codec,
            function_id=0x12,
        ),
        FeatureSpec(
            "noise_control",
            "노이즈 제어",
            b"\x66\x19",
            0x67,
            0x19,
            decode_noise_control,
            function_id=0x6D,
        ),
        FeatureSpec(
            "equalizer",
            "이퀄라이저",
            b"\x56\x04",
            0x57,
            0x04,
            decode_equalizer,
            function_id=0x57,
        ),
        FeatureSpec(
            "dsee",
            "DSEE Extreme",
            b"\xE6\x01",
            0xE7,
            0x01,
            partial(decode_bool, command=0xE7, item_type=0x01),
            Safety.REVERSIBLE,
            function_id=0xE2,
            encoder=encode_dsee,
            write_response_command=0xE9,
            write_response_type=0x01,
            write_decoder=partial(decode_bool, command=0xE9, item_type=0x01),
        ),
        FeatureSpec(
            "auto_pause",
            "착용 감지 자동 일시정지",
            b"\xF6\x01",
            0xF7,
            0x01,
            partial(decode_sony_on_off, command=0xF7, item_type=0x01),
            function_id=0xF1,
        ),
        FeatureSpec(
            "speak_to_chat",
            "Speak-to-Chat",
            b"\xF6\x0C",
            0xF7,
            0x0C,
            decode_speak_to_chat,
            function_id=0xFC,
        ),
        FeatureSpec(
            "connection_mode",
            "Bluetooth 연결 모드",
            b"\xE6\x00",
            0xE7,
            0x00,
            decode_connection_mode,
            function_id=0xE1,
        ),
        FeatureSpec(
            "auto_power_off",
            "착용 감지 자동 전원 끄기",
            b"\x26\x05",
            0x27,
            0x05,
            decode_auto_power_off,
            function_id=0x25,
        ),
        FeatureSpec(
            "voice_guidance",
            "음성 안내",
            b"\x46\x01",
            0x47,
            0x01,
            decode_voice_guidance,
            data_type=DATA_TYPE_MDR_NO2,
            function_id=0x42,
        ),
        FeatureSpec(
            "voice_guidance_volume",
            "음성 안내 음량",
            b"\x46\x20",
            0x47,
            0x20,
            partial(decode_signed_byte, command=0x47, item_type=0x20),
            data_type=DATA_TYPE_MDR_NO2,
            function_id=0x42,
        ),
        FeatureSpec(
            "le_audio_status",
            "LE Audio 연결 상태",
            b"\x62\x00",
            0x63,
            0x00,
            partial(decode_bytes, command=0x63, item_type=0x00),
            data_type=DATA_TYPE_MDR_NO2,
            function_id=0x60,
        ),
        FeatureSpec(
            "le_audio_compatibility",
            "LE Audio 호환 전환",
            b"\x66\x01",
            0x67,
            0x01,
            partial(decode_bytes, command=0x67, item_type=0x01),
            data_type=DATA_TYPE_MDR_NO2,
            function_id=0x61,
        ),
        FeatureSpec(
            "wearing_status",
            "착용 상태",
            b"\xF2\x00",
            0xF3,
            0x00,
            decode_wearing_status,
            data_type=DATA_TYPE_MDR_NO2,
        ),
        FeatureSpec(
            "call_mic_control",
            "통화 중 헤드셋 마이크 조작",
            b"\xF6\x0B",
            0xF7,
            0x0B,
            partial(decode_bytes, command=0xF7, item_type=0x0B),
            data_type=DATA_TYPE_MDR_NO2,
            function_id=0xF9,
        ),
        FeatureSpec(
            "headset_auto_switch",
            "헤드셋 자동 전환",
            b"\xF6\x0A",
            0xF7,
            0x0A,
            partial(decode_bytes, command=0xF7, item_type=0x0A),
            data_type=DATA_TYPE_MDR_NO2,
            function_id=0xF8,
        ),
        FeatureSpec(
            "safe_listening",
            "안전 청취",
            b"\x56\x02",
            0x57,
            0x02,
            partial(decode_sony_on_off, command=0x57, item_type=0x02),
            data_type=DATA_TYPE_MDR_NO2,
            function_id=0x52,
        ),
        FeatureSpec(
            "safe_volume",
            "안전 음량 제어",
            b"\x56\x04",
            0x57,
            0x04,
            partial(decode_sony_on_off, command=0x57, item_type=0x04),
            data_type=DATA_TYPE_MDR_NO2,
            function_id=0x54,
        ),
    )
}


# 쓰기 payload가 실기기에서 왕복 검증되기 전까지 모든 정식 항목은 읽기 전용이다.
DISCOVERY_FEATURES: dict[str, FeatureSpec] = {
    "turn_key_equalizer": FeatureSpec(
        "turn_key_equalizer",
        "전환형 이퀄라이저",
        b"\x56\x32",
        0x57,
        0x32,
        partial(decode_byte, command=0x57, item_type=0x32),
        Safety.EXPERIMENTAL_READ,
        function_id=0x56,
    ),
}
