from __future__ import annotations

import json

from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal, pyqtSlot

from sonus.gui.application import GuiController, web_index_path
from sonus.gui.bridge import GuiBridge
from sonus.gui.settings import GuiSettings
from PyQt6.QtCore import QSettings


class ImmediateWorker(QObject):
    connecting = pyqtSignal()
    connected = pyqtSignal()
    featureReady = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    @pyqtSlot()
    def run(self):
        self.connecting.emit()
        self.connected.emit()
        self.featureReady.emit(json.dumps({"key": "battery", "value": 67}))
        self.finished.emit()


class ImmediateWriteWorker(QObject):
    featureReady = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, mac, channel, key, value):
        super().__init__()
        self.payload = {"key": key, "value": value, "writable": True}

    @pyqtSlot()
    def run(self):
        self.featureReady.emit(json.dumps(self.payload))
        self.finished.emit()


def test_web_index_path_points_to_packaged_interface():
    path = web_index_path()
    assert path.name == "index.html"
    assert path.is_file()


def test_controller_forwards_worker_events_to_read_only_bridge(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    settings = GuiSettings(
        QSettings(str(tmp_path / "sonus.ini"), QSettings.Format.IniFormat)
    )
    bridge = GuiBridge(settings)
    controller = GuiController(bridge, worker_factory=lambda *_: ImmediateWorker())
    connections = []
    features = []
    finished = []
    bridge.connectionState.connect(lambda value: connections.append(json.loads(value)))
    bridge.featureState.connect(features.append)
    bridge.refreshFinished.connect(lambda: finished.append(True))

    controller.start_read("AA:BB:CC:DD:EE:FF", 9)
    deadline = 100
    while not finished and deadline:
        app.processEvents()
        deadline -= 1

    assert [item["state"] for item in connections] == ["connecting", "connected"]
    assert json.loads(features[0])["key"] == "battery"
    assert finished == [True]


def test_controller_rejects_overlapping_refresh(tmp_path):
    settings = GuiSettings(
        QSettings(str(tmp_path / "sonus.ini"), QSettings.Format.IniFormat)
    )
    bridge = GuiBridge(settings)
    messages = []
    bridge.userMessage.connect(messages.append)
    controller = GuiController(bridge, worker_factory=lambda *_: ImmediateWorker())
    controller._busy = True

    controller.start_read("AA:BB:CC:DD:EE:FF", 9)

    assert messages == ["이미 헤드셋 정보를 읽고 있습니다."]


def test_controller_forwards_verified_write_result(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    settings = GuiSettings(QSettings(str(tmp_path / "sonus.ini"), QSettings.Format.IniFormat))
    settings.device_mac = "AA:BB:CC:DD:EE:FF"
    settings.channel = 9
    bridge = GuiBridge(settings)
    controller = GuiController(
        bridge,
        write_worker_factory=lambda *args: ImmediateWriteWorker(*args),
    )
    features = []
    finished = []
    bridge.featureState.connect(lambda payload: features.append(json.loads(payload)))
    bridge.refreshFinished.connect(lambda: finished.append(True))

    controller.start_write("dsee", "false")
    deadline = 100
    while not finished and deadline:
        app.processEvents()
        deadline -= 1

    assert features == [{"key": "dsee", "value": False, "writable": True}]


def test_controller_lists_and_deduplicates_saved_bluetooth_devices(tmp_path):
    settings = GuiSettings(QSettings(str(tmp_path / "sonus.ini"), QSettings.Format.IniFormat))
    settings.remember_device("AA:BB:CC:DD:EE:FF", 9, "저장된 XM6")
    bridge = GuiBridge(settings)
    controller = GuiController(
        bridge,
        device_lister=lambda: "Device AA:BB:CC:DD:EE:FF WH-1000XM6\nDevice 11:22:33:44:55:66 TV\n",
    )
    payloads = []
    bridge.devicesState.connect(lambda payload: payloads.append(json.loads(payload)))

    bridge.requestDevices()

    assert controller is not None
    assert [item["mac"] for item in payloads[0]] == [
        "AA:BB:CC:DD:EE:FF",
        "11:22:33:44:55:66",
    ]
