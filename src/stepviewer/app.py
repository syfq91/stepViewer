"""Application entry point."""

from __future__ import annotations

import os
import sys

# VTK looks this up when it imports its Qt bindings, so it has to be set first.
os.environ.setdefault("QT_API", "pyside6")


def _apply_dark_palette(app) -> None:
    from PySide6.QtGui import QColor, QPalette

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#232831"))
    palette.setColor(QPalette.WindowText, QColor("#e6e9ef"))
    palette.setColor(QPalette.Base, QColor("#1b1f27"))
    palette.setColor(QPalette.AlternateBase, QColor("#222833"))
    palette.setColor(QPalette.Text, QColor("#e6e9ef"))
    palette.setColor(QPalette.Button, QColor("#2b313b"))
    palette.setColor(QPalette.ButtonText, QColor("#e6e9ef"))
    palette.setColor(QPalette.Highlight, QColor("#3d7eff"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase, QColor("#2b313b"))
    palette.setColor(QPalette.ToolTipText, QColor("#e6e9ef"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#6b7280"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#6b7280"))
    app.setPalette(palette)


def main(argv: list[str] | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    from .config import APP_NAME
    from .ui.main_window import MainWindow

    args = list(sys.argv if argv is None else argv)
    application = QApplication(args)
    application.setApplicationName(APP_NAME)
    application.setApplicationDisplayName(APP_NAME)
    application.setOrganizationName(APP_NAME)
    application.setStyle("Fusion")
    _apply_dark_palette(application)

    window = MainWindow()
    if len(args) > 1:
        window.open_paths(args[1:])
    window.show()
    return application.exec()
