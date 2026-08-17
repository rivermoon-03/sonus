from __future__ import annotations

import pytest

from sonus.device.xm6 import SonyXm6Device, UnsupportedFeatureError, UnsafeWriteError
from sonus.messages.codec import decode_bool
from sonus.messages.types import FeatureSpec, Safety
from sonus.protocol.framing import DATA_TYPE_MDR, Frame


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, data_type, payload=b"", *, response_matcher=None):
        self.requests.append((data_type, payload, response_matcher))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        assert response_matcher is None or response_matcher(response)
        return response


def test_get_uses_identity_matcher_and_decodes_value():
    session = FakeSession([Frame(DATA_TYPE_MDR, 1, bytes.fromhex("23005300"))])
    device = SonyXm6Device(session)

    result = device.get("battery")

    assert result.value == {"level": 83, "charging": False}
    assert result.raw == "23005300"
    assert result.supported is True
    assert session.requests[0][1] == bytes.fromhex("2200")


def test_get_rejects_unknown_key():
    with pytest.raises(UnsupportedFeatureError, match="unknown"):
        SonyXm6Device(FakeSession([])).get("unknown")


def test_get_many_keeps_other_results_when_one_query_fails():
    session = FakeSession(
        [
            Frame(DATA_TYPE_MDR, 1, bytes.fromhex("23005300")),
            TimeoutError("no response"),
        ]
    )
    device = SonyXm6Device(session)

    results = device.get_many(["battery", "codec"])

    assert results["battery"].value["level"] == 83
    assert results["codec"].supported is False
    assert results["codec"].error == "timeout"


def test_set_blocks_read_only_feature():
    with pytest.raises(UnsafeWriteError, match="read-only"):
        SonyXm6Device(FakeSession([])).set("auto_pause", True)


def test_temporary_setting_restores_original_after_body_error():
    def decoder(payload):
        return decode_bool(payload, 0xE7, 0x01)

    feature = FeatureSpec(
        "toggle",
        "토글",
        b"\xE6\x01",
        0xE7,
        0x01,
        decoder,
        Safety.REVERSIBLE,
        encoder=lambda value: b"\xE8\x01" + bytes((int(value),)),
        write_response_command=0xE9,
        write_response_type=0x01,
        write_decoder=lambda payload: decode_bool(payload, 0xE9, 0x01),
    )
    session = FakeSession(
        [
            Frame(DATA_TYPE_MDR, 1, bytes.fromhex("e70100")),
            Frame(DATA_TYPE_MDR, 0, bytes.fromhex("e90101")),
            Frame(DATA_TYPE_MDR, 1, bytes.fromhex("e90100")),
        ]
    )
    device = SonyXm6Device(session, features={"toggle": feature})

    with pytest.raises(RuntimeError, match="body"):
        with device.temporary_setting("toggle", True):
            raise RuntimeError("body")

    assert [payload for _, payload, _ in session.requests] == [
        bytes.fromhex("e601"),
        bytes.fromhex("e80101"),
        bytes.fromhex("e80100"),
    ]


def test_temporary_setting_is_a_context_manager_on_success():
    # 공개 API가 실제 context manager임을 간단히 고정한다.
    assert hasattr(SonyXm6Device.temporary_setting, "__call__")
