from __future__ import annotations

import json

from PyQt6.QtCore import QSettings

from sonus.gui.bridge import GuiBridge
from sonus.gui.settings import GuiSettings


def make_bridge(tmp_path):
    backend = QSettings(str(tmp_path / "sonus.ini"), QSettings.Format.IniFormat)
    backend.clear()
    return GuiBridge(GuiSettings(backend))


def test_bridge_emits_initial_state_with_disclaimer_and_saved_devices(tmp_path):
    bridge = make_bridge(tmp_path)
    payloads = []
    bridge.initialState.connect(payloads.append)

    bridge.requestInitialState()

    assert json.loads(payloads[0]) == {
        "channel": None,
        "mac": "",
        "disclaimerAccepted": False,
        "readOnly": False,
        "savedDevices": [],
        "theme": "light",
    }


def test_bridge_normalizes_valid_connect_request_and_persists_it(tmp_path):
    bridge = make_bridge(tmp_path)
    requests = []
    bridge.connectRequested.connect(lambda mac, channel: requests.append((mac, channel)))

    bridge.connectDevice("aa:bb:cc:dd:ee:ff", 9)

    assert requests == [("AA:BB:CC:DD:EE:FF", 9)]
    assert bridge.settings.device_mac == "AA:BB:CC:DD:EE:FF"
    assert bridge.settings.channel == 9


def test_bridge_rejects_invalid_mac_without_starting_connection(tmp_path):
    bridge = make_bridge(tmp_path)
    requests = []
    messages = []
    bridge.connectRequested.connect(lambda *args: requests.append(args))
    bridge.userMessage.connect(messages.append)

    bridge.connectDevice("not-a-mac", 9)

    assert requests == []
    assert messages == ["Bluetooth 주소를 확인해 주세요."]


def test_refresh_without_saved_device_is_explained(tmp_path):
    bridge = make_bridge(tmp_path)
    messages = []
    bridge.userMessage.connect(messages.append)

    bridge.refresh()

    assert messages == ["먼저 헤드셋을 연결해 주세요."]


def test_bridge_saves_theme(tmp_path):
    bridge = make_bridge(tmp_path)

    bridge.saveTheme("dark")

    assert bridge.settings.theme == "dark"
    assert bridge.settings.theme == "dark"


def test_bridge_persists_disclaimer_and_emits_verified_write_request(tmp_path):
    bridge = make_bridge(tmp_path)
    requests = []
    bridge.featureWriteRequested.connect(
        lambda key, value: requests.append((key, json.loads(value)))
    )

    bridge.acceptDisclaimer()
    bridge.setFeature("dsee", "false")

    assert bridge.settings.disclaimer_accepted is True
    assert requests == [("dsee", False)]


def test_bridge_rejects_write_before_disclaimer_or_for_read_only_feature(tmp_path):
    bridge = make_bridge(tmp_path)
    requests = []
    messages = []
    bridge.featureWriteRequested.connect(lambda *args: requests.append(args))
    bridge.userMessage.connect(messages.append)

    bridge.setFeature("dsee", "true")
    bridge.acceptDisclaimer()
    # safe_listening's GET reflects device support, not a stored setting, so it
    # can never be write-verified and stays permanently read-only (unlike
    # noise_control, which is conditionally writable while worn).
    bridge.setFeature("safe_listening", '{}')

    assert requests == []
    assert messages == [
        "설정 변경 안내에 먼저 동의해 주세요.",
        "이 설정은 안전한 쓰기가 검증되지 않았습니다.",
    ]


def test_bridge_rejects_malformed_write_value(tmp_path):
    bridge = make_bridge(tmp_path)
    messages = []
    bridge.userMessage.connect(messages.append)
    bridge.acceptDisclaimer()

    bridge.setFeature("dsee", "not-json")

    assert messages == ["설정값을 확인해 주세요."]


def test_bridge_requests_bluetooth_device_listing(tmp_path):
    bridge = make_bridge(tmp_path)
    requests = []
    bridge.devicesRequested.connect(lambda: requests.append(True))

    bridge.requestDevices()

    assert requests == [True]


def test_bridge_requests_debug_state(tmp_path):
    bridge = make_bridge(tmp_path)
    requests = []
    bridge.debugRequested.connect(lambda: requests.append(True))

    bridge.requestDebugState()

    assert requests == [True]


def test_named_device_connection_is_saved_for_later_selection(tmp_path):
    bridge = make_bridge(tmp_path)
    requests = []
    bridge.connectRequested.connect(lambda mac, channel: requests.append((mac, channel)))

    bridge.connectNamedDevice("aa:bb:cc:dd:ee:ff", 9, "WH-1000XM6")

    assert requests == [("AA:BB:CC:DD:EE:FF", 9)]
    assert bridge.settings.saved_devices == [
        {"mac": "AA:BB:CC:DD:EE:FF", "channel": 9, "name": "WH-1000XM6"}
    ]
