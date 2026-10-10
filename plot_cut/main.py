"""Einstiegspunkt: startet das Panel, Tray-Icon und globales Tastenkuerzel."""

from __future__ import annotations

import sys

from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import i18n
from .app import AppController
from .ui import icons
from .ui.panel import Panel


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Plot Cut")
    app.setWindowIcon(icons.app_icon())
    app.setQuitOnLastWindowClosed(False)

    controller = AppController()
    panel = Panel(controller)
    controller.panel = panel
    controller.restore_panel_geometry()
    panel.show()

    # Tastenkuerzel: Strg+Alt+P loest Plot aus (wenn das Panel den Fokus hat).
    shortcut = QShortcut(QKeySequence("Ctrl+Alt+P"), panel)
    shortcut.activated.connect(controller.on_plot)

    tray = _build_tray(app, controller, panel)
    tray.show()

    return app.exec()


def _build_tray(app: QApplication, controller: AppController, panel: Panel) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(icons.app_icon(), parent=app)
    tray.setToolTip("Plot Cut")

    menu = QMenu()

    act_show = QAction(menu)
    i18n.bind(act_show, text="Panel anzeigen")
    act_show.triggered.connect(panel.show)
    act_show.triggered.connect(panel.raise_)
    menu.addAction(act_show)

    act_plot = QAction(menu)
    i18n.bind(act_plot, text="Plot ...")
    act_plot.triggered.connect(controller.on_plot)
    menu.addAction(act_plot)

    act_setup = QAction(menu)
    i18n.bind(act_setup, text="Setup ...")
    act_setup.triggered.connect(controller.on_setup)
    menu.addAction(act_setup)

    act_test = QAction(menu)
    i18n.bind(act_test, text="Verbindung testen")
    act_test.triggered.connect(controller.on_test_connection)
    menu.addAction(act_test)

    menu.addSeparator()
    act_quit = QAction(menu)
    i18n.bind(act_quit, text="Beenden")
    act_quit.triggered.connect(app.quit)
    menu.addAction(act_quit)
    i18n.watch(menu)

    tray.setContextMenu(menu)

    def _on_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            panel.show()
            panel.raise_()

    tray.activated.connect(_on_activated)
    return tray


if __name__ == "__main__":
    raise SystemExit(main())
