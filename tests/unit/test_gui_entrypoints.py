from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_root_launcher_and_src_entrypoint_exist():
    launcher = ROOT / "run.sh"
    entrypoint = ROOT / "src" / "main.py"

    assert launcher.is_file()
    assert launcher.stat().st_mode & 0o111
    assert "uv run python src/main.py" in launcher.read_text(encoding="utf-8")
    assert "sonus.gui.main import main" in entrypoint.read_text(encoding="utf-8")
