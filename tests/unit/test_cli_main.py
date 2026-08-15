from sonus.cli import main as cli_main
from sonus.protocol.session import ProtocolTimeoutError


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
