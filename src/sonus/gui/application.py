"""PyQt6 application shell for the Sonus control interface."""

from __future__ import annotations

import os
import json
import subprocess
from importlib.resources import files
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, QThread, QUrl, pyqtSlot
from PyQt6.QtGui import QAction, QColor, QCloseEvent, QIcon, QPainter, QPixmap
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow, QMenu, QSystemTrayIcon

from sonus.gui.bridge import GuiBridge
from sonus.gui.devices import parse_bluetoothctl_devices
from sonus.gui.settings import GuiSettings
from sonus.gui.worker import DeviceReadWorker, DeviceWriteWorker


def web_index_path() -> Path:
    """Return the installed web entry point (wheels are extracted before import)."""
    return Path(os.fspath(files("sonus.gui").joinpath("web", "index.html")))


class GuiController(QObject):
    """Own one device reader thread and forward only read results to the bridge."""

    def __init__(
        self,
        bridge: GuiBridge,
        *,
        worker_factory: Callable[[str, int], QObject] = DeviceReadWorker,
        write_worker_factory: Callable[..., QObject] = DeviceWriteWorker,
        device_lister: Callable[[], str] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self._worker_factory = worker_factory
        self._write_worker_factory = write_worker_factory
        self._device_lister = device_lister or self._list_devices
        self._thread: QThread | None = None
        self._worker: QObject | None = None
        self._busy = False
        bridge.connectRequested.connect(self.start_read)
        bridge.featureWriteRequested.connect(self.start_write)
        bridge.devicesRequested.connect(self.list_devices)

    @staticmethod
    def _list_devices() -> str:
        result = subprocess.run(
            ["bluetoothctl", "devices"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout

    @pyqtSlot()
    def list_devices(self) -> None:
        try:
            discovered = parse_bluetoothctl_devices(self._device_lister())
        except (OSError, subprocess.SubprocessError):
            discovered = []
        by_mac = {str(item["mac"]): item for item in self.bridge.settings.saved_devices}
        for item in discovered:
            by_mac.setdefault(str(item["mac"]), item)
        self.bridge.devicesState.emit(json.dumps(list(by_mac.values()), ensure_ascii=False))

    @pyqtSlot(str, int)
    def start_read(self, mac: str, channel: int) -> None:
        if self._busy:
            self.bridge.userMessage.emit("이미 헤드셋 정보를 읽고 있습니다.")
            return
        self._busy = True
        thread = QThread(self)
        worker = self._worker_factory(mac, channel)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.connecting.connect(lambda: self.bridge.emit_connection("connecting"))
        worker.connected.connect(lambda: self.bridge.emit_connection("connected"))
        worker.featureReady.connect(self.bridge.featureState.emit)
        worker.failed.connect(lambda message: self.bridge.emit_connection("failed", message))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._read_finished)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    @pyqtSlot()
    def _read_finished(self) -> None:
        self._busy = False
        self._worker = None
        self._thread = None
        self.bridge.refreshFinished.emit()

    @pyqtSlot(str, str)
    def start_write(self, key: str, encoded_value: str) -> None:
        if self._busy:
            self.bridge.userMessage.emit("다른 작업이 진행 중입니다.")
            return
        mac = self.bridge.settings.device_mac
        channel = self.bridge.settings.channel
        if not mac or channel is None:
            self.bridge.userMessage.emit("먼저 헤드셋을 연결해 주세요.")
            return
        self._busy = True
        thread = QThread(self)
        worker = self._write_worker_factory(mac, channel, key, json.loads(encoded_value))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.featureReady.connect(self.bridge.featureState.emit)
        worker.failed.connect(self.bridge.userMessage.emit)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._write_finished)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    @pyqtSlot()
    def _write_finished(self) -> None:
        self._busy = False
        self._worker = None
        self._thread = None
        self.bridge.refreshFinished.emit()


def application_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#2563eb"))
    painter.setPen(QColor("transparent"))
    painter.drawRoundedRect(4, 4, 56, 56, 16, 16)
    painter.setPen(QColor("white"))
    for x, height in ((25, 17), (32, 30), (39, 22)):
        painter.setPen(QColor("white"))
        painter.drawLine(x, 32 - height // 2, x, 32 + height // 2)
    painter.end()
    return QIcon(pixmap)


class SonusWindow(QMainWindow):
    def __init__(self, settings: GuiSettings, parent=None) -> None:
        super().__init__(parent)
        self.settings_store = settings
        self.bridge = GuiBridge(settings, self)
        self.controller = GuiController(self.bridge, parent=self)
        self.bridge.quitRequested.connect(self.quit_application)
        self._really_quit = False
        self.setWindowTitle("Sonus · WH-1000XM6")
        self.setWindowIcon(application_icon())
        self.resize(1180, 780)
        self.setMinimumSize(800, 620)
        if geometry := settings.window_geometry:
            self.restoreGeometry(geometry)

        self.web_view = QWebEngineView(self)
        self.web_view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        self.channel = QWebChannel(self.web_view.page())
        self.channel.registerObject("sonusBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        self.web_view.load(QUrl.fromLocalFile(str(web_index_path())))
        self.setCentralWidget(self.web_view)

        self.tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._create_tray()

    def _create_tray(self) -> None:
        self.tray = QSystemTrayIcon(application_icon(), self)
        self.tray.setToolTip("Sonus · WH-1000XM6 제어")
        menu = QMenu()
        show_action = QAction("Sonus 열기", menu)
        show_action.triggered.connect(self.show_from_tray)
        quit_action = QAction("종료", menu)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.show_from_tray()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        self.tray.show()

    @pyqtSlot()
    def show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    @pyqtSlot()
    def quit_application(self) -> None:
        self._really_quit = True
        self.settings_store.window_geometry = bytes(self.saveGeometry())
        if self.tray:
            self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings_store.window_geometry = bytes(self.saveGeometry())
        if self.tray and not self._really_quit:
            event.ignore()
            self.hide()
            self.tray.showMessage("Sonus", "백그라운드에서 계속 실행 중입니다.")
        else:
            event.accept()
