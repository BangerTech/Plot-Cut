"""Das schwebende FineCut-aehnliche Panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import i18n
from . import icons
from .style import ComboBox

if TYPE_CHECKING:
    from ..app import AppController


class Panel(QWidget):
    """Kleines, immer im Vordergrund liegendes Werkzeugfenster."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self._drag_offset: QPoint | None = None

        self.setWindowTitle("Plot Cut")
        self.setWindowFlags(
            Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setObjectName("PlotPanel")
        self.setStyleSheet(_STYLE)

        self._build_ui()
        self.setFixedWidth(292)
        self._status_source = ("Bereit", {})
        i18n.watch(self)

    # -- Aufbau ------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_profile_row())
        root.addWidget(self._build_grid())
        root.addWidget(self._build_status())

    def _build_profile_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("Body")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 8, 10, 0)
        label = QLabel()
        i18n.bind(label, text="Plotter")
        label.setObjectName("Status")
        lay.addWidget(label)
        self.profile_combo = ComboBox()
        i18n.bind(self.profile_combo, tip="Aktiven Plotter wählen")
        self.profile_combo.currentTextChanged.connect(self._on_profile_changed)
        lay.addWidget(self.profile_combo, 1)
        self.reload_profiles()
        return row

    def reload_profiles(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(self.controller.profile_names())
        self.profile_combo.setCurrentText(self.controller.profile_name)
        self.profile_combo.blockSignals(False)

    def _on_profile_changed(self, name: str) -> None:
        if name:
            self.controller.switch_profile(name)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("Header")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(8, 6, 8, 6)

        logo = QLabel()
        logo.setPixmap(icons.app_icon().pixmap(32, 32))
        lay.addWidget(logo)

        title = QLabel("Plot Cut")
        f = QFont()
        f.setBold(True)
        title.setFont(f)
        title.setObjectName("Title")
        lay.addWidget(title)
        lay.addStretch(1)

        info_btn = QToolButton()
        info_btn.setIcon(icons.icon_info())
        i18n.bind(info_btn, tip="Info / Verbindung")
        info_btn.clicked.connect(self.controller.show_info)
        lay.addWidget(info_btn)

        close_btn = QToolButton()
        close_btn.setText("x")
        close_btn.setObjectName("CloseBtn")
        i18n.bind(close_btn, tip="Panel schliessen")
        close_btn.clicked.connect(self.hide)
        lay.addWidget(close_btn)

        return header

    def _build_grid(self) -> QWidget:
        body = QFrame()
        body.setObjectName("Body")
        grid = QGridLayout(body)
        grid.setContentsMargins(10, 10, 10, 6)
        grid.setSpacing(6)

        # (label, icon, tooltip, handler, enabled)
        buttons = [
            ("Plot", icons.icon_plot(), "Auswahl schneiden (Plot)", self.controller.on_plot, True),
            ("Setup", icons.icon_setup(), "Plotter/User Setup", self.controller.on_setup, True),
            ("Test", icons.icon_test(), "Verbindung testen", self.controller.on_test_connection, True),
            ("Kontur", icons.icon_generic("K"), "Äußerste Kante der Kontur als Schnittlinie", self.controller.on_contour, True),
            ("Entgittern", icons.icon_generic("E"), "Entgitterlinien (folgt)", None, False),
            ("Cut-Ebene", icons.icon_generic("C"), "Auf Cut-Ebene verschieben (folgt)", None, False),
            ("Marken", icons.icon_generic("M"), "Passermarken (folgt)", None, False),
            ("Line Edit", icons.icon_generic("L"), "Linien bearbeiten (folgt)", None, False),
            ("RasterLink", icons.icon_generic("R"), "Ausgabe an RasterLink (folgt)", None, False),
        ]

        cols = 3
        for i, (label, icon, tip, handler, enabled) in enumerate(buttons):
            grid.addWidget(_tile(label, icon, tip, handler, enabled), i // cols, i % cols)

        return body

    def _build_status(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 3, 8, 3)
        self.status_label = QLabel()
        self.status_label.setObjectName("Status")
        lay.addWidget(self.status_label)
        self.set_status("Bereit")
        return bar

    def set_status(self, text: str, **fmt: object) -> None:
        self._status_source = (text, fmt)
        self.status_label._i18n_status = (text, fmt)  # noqa: SLF001
        self.status_label.setText(i18n.trf(text, **fmt))

    # -- Fenster verschieben (rahmenlos) -----------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        self.controller.save_panel_geometry()


def _tile(label: str, icon, tip: str, handler, enabled: bool) -> QPushButton:
    """Kachel mit Icon und Text, beide in der Mitte der Box."""
    btn = QPushButton()
    btn.setObjectName("Tile")
    btn.setFixedSize(86, 68)
    i18n.bind(btn, tip=tip)
    btn.setEnabled(enabled)
    btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
    lay = QVBoxLayout(btn)
    lay.setContentsMargins(4, 6, 4, 6)
    lay.setSpacing(2)
    lay.addStretch(1)
    pic = QLabel()
    pic.setPixmap(icon.pixmap(22, 22))
    pic.setAlignment(Qt.AlignCenter)
    pic.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    text = QLabel()
    i18n.bind(text, text=label)
    text.setObjectName("TileText")
    text.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
    text.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    lay.addWidget(pic)
    lay.addWidget(text)
    lay.addStretch(1)
    if handler is not None:
        btn.clicked.connect(handler)
    return btn


_STYLE = """
#PlotPanel { background: #3a3a3a; border: 1px solid #222; }
#Header { background: #2b2b2b; }
#Body { background: #3a3a3a; }
#StatusBar { background: #2b2b2b; }
QLabel#Title { color: #f0f0f0; }
QLabel#Status { color: #b8b8b8; font-size: 11px; }
QPushButton#Tile {
    color: #e8e8e8; background: #454545; border: 1px solid #2d2d2d;
    border-radius: 4px;
}
QPushButton#Tile:hover:enabled { background: #525252; }
QPushButton#Tile:pressed:enabled { background: #5d5d5d; }
QPushButton#Tile:disabled { color: #888; background: #3f3f3f; }
QPushButton#Tile QLabel#TileText {
    color: #e8e8e8; background: transparent; font-size: 11px;
}
QPushButton#Tile:disabled QLabel#TileText { color: #888; }
QToolButton {
    color: #e8e8e8; background: #454545; border: 1px solid #2d2d2d;
    border-radius: 4px; font-size: 10px;
}
QToolButton:hover:enabled { background: #525252; }
QToolButton:pressed:enabled { background: #5d5d5d; }
QToolButton:disabled { color: #888; background: #3f3f3f; }
QToolButton#CloseBtn { min-width: 20px; max-width: 20px; }
QComboBox {
    color: #e8e8e8; background: #454545; border: 1px solid #2d2d2d;
    border-radius: 4px; padding: 2px 6px;
}
"""
