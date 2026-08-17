import json

from sonus.cli import main as cli_main
from sonus.cli.device import format_results, parse_value
from sonus.device.xm6 import FeatureResult
from sonus.protocol.session import ProtocolTimeoutError


def test_status_dispatches_common_connection_arguments(monkeypatch, capsys):
    called = {}

    def fake(mac, channel, *, as_json):
        called.update(mac=mac, channel=channel, as_json=as_json)
        return "ok"

    monkeypatch.setattr(cli_main, "run_status", fake)

    result = cli_main.main(
        ["status", "--mac", "AA:BB:CC:DD:EE:FF", "--channel", "9", "--json"]
    )

    assert result == 0
    assert capsys.readouterr().out == "ok\n"
    assert called == {"mac": "AA:BB:CC:DD:EE:FF", "channel": 9, "as_json": True}


def test_get_requires_feature_key(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_main,
        "run_get",
        lambda mac, channel, key, *, as_json: key,
    )

    assert cli_main.main(["get", "--mac", "AA", "battery"]) == 0
    assert capsys.readouterr().out == "battery\n"


def test_parse_value_accepts_common_cli_values():
    assert parse_value("on") is True
    assert parse_value("false") is False
    assert parse_value("12") == 12
    assert parse_value('[1, 2]') == [1, 2]
    assert parse_value("ambient") == "ambient"


def test_format_results_json_has_stable_keys():
    output = format_results(
        {"battery": FeatureResult("battery", "배터리", {"level": 83})},
        as_json=True,
    )

    assert json.loads(output)["battery"] == {
        "key": "battery",
        "label": "배터리",
        "value": {"level": 83},
        "supported": True,
        "writable": False,
        "raw": None,
        "error": None,
    }


def test_format_results_text_marks_unsupported_item():
    output = format_results(
        {"codec": FeatureResult("codec", "코덱", supported=False, error="timeout")},
        as_json=False,
    )

    assert output == "코덱 (codec): 미확인 [timeout]"


def test_format_results_text_uses_plain_korean_values():
    output = format_results(
        {
            "connection_mode": FeatureResult(
                "connection_mode", "연결 모드", "sound_quality"
            ),
            "dsee": FeatureResult("dsee", "DSEE", True),
            "wearing_status": FeatureResult("wearing_status", "착용", "not_worn"),
        },
        as_json=False,
    )

    assert output.splitlines() == [
        "연결 모드 (connection_mode): 음질 우선",
        "DSEE (dsee): 자동",
        "착용 (wearing_status): 착용하지 않음",
    ]


def test_main_converts_timeout_to_short_user_message(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise ProtocolTimeoutError("internal detail")

    monkeypatch.setattr(cli_main, "run_probe", fail)

    result = cli_main.main(["probe", "--mac", "58:18:62:1F:C9:CB"])

    captured = capsys.readouterr()
    assert result == 1
    assert "응답 시간이 초과" in captured.err
    assert "Traceback" not in captured.err
    assert "internal detail" not in captured.err
