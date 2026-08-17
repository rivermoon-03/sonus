"""Desktop entry point."""

from __future__ import annotations

import argparse
import sys

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from sonus.gui.application import SonusWindow, application_icon
from sonus.gui.settings import GuiSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sonus WH-1000XM6 control GUI")
    parser.add_argument("--mac", help="Bluetooth MAC address")
    parser.add_argument("--channel", type=int, help="RFCOMM channel")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    QCoreApplication.setOrganizationName("Sonus")
    QCoreApplication.setApplicationName("Sonus")
    app = QApplication(sys.argv[:1])
    app.setApplicationDisplayName("Sonus")
    app.setWindowIcon(application_icon())
    settings = GuiSettings()
    if args.mac:
        settings.device_mac = args.mac
    if args.channel is not None:
        settings.channel = args.channel
    window = SonusWindow(settings)
    if QSystemTrayIcon.isSystemTrayAvailable():
        app.setQuitOnLastWindowClosed(False)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
