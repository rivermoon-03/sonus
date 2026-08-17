from __future__ import annotations

from PyQt6.QtCore import QSettings

from sonus.gui.settings import GuiSettings


def make_settings(tmp_path):
    backend = QSettings(str(tmp_path / "sonus.ini"), QSettings.Format.IniFormat)
    backend.clear()
    return GuiSettings(backend)


def test_settings_default_to_light_and_no_device(tmp_path):
    settings = make_settings(tmp_path)

    assert settings.theme == "light"
    assert settings.device_mac == ""
    assert settings.channel is None


def test_settings_normalize_and_persist_device_and_theme(tmp_path):
    path = tmp_path / "sonus.ini"
    settings = GuiSettings(QSettings(str(path), QSettings.Format.IniFormat))
    settings.device_mac = "aa:bb:cc:dd:ee:ff"
    settings.channel = 9
    settings.theme = "dark"

    restored = GuiSettings(QSettings(str(path), QSettings.Format.IniFormat))
    assert restored.device_mac == "AA:BB:CC:DD:EE:FF"
    assert restored.channel == 9
    assert restored.theme == "dark"


def test_settings_sanitize_invalid_stored_values(tmp_path):
    backend = QSettings(str(tmp_path / "sonus.ini"), QSettings.Format.IniFormat)
    backend.setValue("appearance/theme", "sepia")
    backend.setValue("device/channel", "invalid")
    settings = GuiSettings(backend)

    assert settings.theme == "light"
    assert settings.channel is None


def test_settings_remember_multiple_devices_and_deduplicate_by_mac(tmp_path):
    path = tmp_path / "sonus.ini"
    settings = GuiSettings(QSettings(str(path), QSettings.Format.IniFormat))

    settings.remember_device("aa:bb:cc:dd:ee:ff", 9, "거실 XM6")
    settings.remember_device("11:22:33:44:55:66", 7, "업무용 헤드셋")
    settings.remember_device("AA:BB:CC:DD:EE:FF", 10, "WH-1000XM6")

    restored = GuiSettings(QSettings(str(path), QSettings.Format.IniFormat))
    assert restored.saved_devices == [
        {"mac": "AA:BB:CC:DD:EE:FF", "channel": 10, "name": "WH-1000XM6"},
        {"mac": "11:22:33:44:55:66", "channel": 7, "name": "업무용 헤드셋"},
    ]


def test_disclaimer_acceptance_is_false_once_then_persisted(tmp_path):
    path = tmp_path / "sonus.ini"
    settings = GuiSettings(QSettings(str(path), QSettings.Format.IniFormat))
    assert settings.disclaimer_accepted is False

    settings.disclaimer_accepted = True

    restored = GuiSettings(QSettings(str(path), QSettings.Format.IniFormat))
    assert restored.disclaimer_accepted is True
