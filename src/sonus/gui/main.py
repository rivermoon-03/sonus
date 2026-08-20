"""Desktop entry point."""

from __future__ import annotations

import argparse
import signal
import sys
from typing import Callable

from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from sonus.gui.application import SonusWindow, application_icon
from sonus.gui.settings import GuiSettings

_SINGLE_INSTANCE_KEY = "sonus-gui-single-instance"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sonus WH-1000XM6 control GUI")
    parser.add_argument("--mac", help="Bluetooth MAC address")
    parser.add_argument("--channel", type=int, help="RFCOMM channel")
    return parser


def _notify_running_instance() -> bool:
    """Return True if another instance answered (and was told to raise itself)."""
    socket = QLocalSocket()
    socket.connectToServer(_SINGLE_INSTANCE_KEY)
    if socket.waitForConnected(200):
        socket.write(b"raise")
        socket.waitForBytesWritten(200)
        socket.disconnectFromServer()
        return True
    return False


def _start_instance_server(on_raise: Callable[[], None]) -> QLocalServer:
    # Removes a stale socket left behind by a crashed previous instance --
    # without this, listen() below would fail with "address already in use"
    # and every future launch would look like a duplicate is already running.
    QLocalServer.removeServer(_SINGLE_INSTANCE_KEY)
    server = QLocalServer()
    server.listen(_SINGLE_INSTANCE_KEY)

    def handle_connection() -> None:
        connection = server.nextPendingConnection()
        if connection is None:
            return
        connection.readyRead.connect(lambda: (connection.readAll(), on_raise()))
        connection.disconnected.connect(connection.deleteLater)

    server.newConnection.connect(handle_connection)
    return server


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    QCoreApplication.setOrganizationName("Sonus")
    QCoreApplication.setApplicationName("Sonus")
    app = QApplication(sys.argv[:1])
    app.setApplicationDisplayName("Sonus")
    app.setWindowIcon(application_icon())

    # Closing the window backgrounds the app to the tray instead of exiting
    # (see SonusWindow.closeEvent), so relaunching the launcher without this
    # guard would spawn a second live process -- and a second tray icon --
    # rather than reattaching to the one already running.
    if _notify_running_instance():
        return 0

    settings = GuiSettings()
    if args.mac:
        settings.device_mac = args.mac
    if args.channel is not None:
        settings.channel = args.channel
    window = SonusWindow(settings)
    instance_server = _start_instance_server(window.show_from_tray)
    if QSystemTrayIcon.isSystemTrayAvailable():
        app.setQuitOnLastWindowClosed(False)

    # aboutToQuit fires on every quit path (tray menu, Cmd/Ctrl+Q, signals
    # below), so the tray icon always gets torn down instead of lingering
    # as an orphaned entry when something other than quit_application()
    # ends the process.
    app.aboutToQuit.connect(lambda: window.tray.hide() if window.tray else None)

    # PyQt6's event loop blocks Python's default SIGINT/SIGTERM handling;
    # without this, Ctrl+C in the launching terminal can appear to do
    # nothing while the loop is idle, and a wakeup timer is needed so the
    # interpreter actually gets a chance to run the handler below.
    def handle_signal(*_args: object) -> None:
        window.quit_application()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    signal_wakeup = QTimer()
    signal_wakeup.timeout.connect(lambda: None)
    signal_wakeup.start(200)

    window.show()
    exit_code = app.exec()
    instance_server.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
