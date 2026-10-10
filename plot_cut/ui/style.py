"""Helles FineCut-Stylesheet. Eigene Datei, damit sich die Dialoge nicht
gegenseitig importieren."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QComboBox, QListView

# Dropdown der Combobox: eigene Top-Level-Fenster, sonst unsichtbar hinter
# einem immer-oben-Dialog, und unter Windows-Dunkelmodus weiss auf weiss.
_POPUP_STYLE = """
QListView {
    color: #111111; background: #ffffff; outline: none; border: 1px solid #b8b8b8;
}
QListView::item { color: #111111; background: #ffffff; padding: 4px 8px; min-height: 22px; }
QListView::item:selected { color: #111111; background: #d7eadc; }
"""


class ComboBox(QComboBox):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        view = QListView()
        view.setStyleSheet(_POPUP_STYLE)
        palette = view.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor("#111111"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#d7eadc"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#111111"))
        view.setPalette(palette)
        self.setView(view)

    def showPopup(self) -> None:
        super().showPopup()
        popup = self.view().window()
        geo = popup.geometry()
        popup.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        popup.setGeometry(geo)
        popup.show()
        popup.raise_()

# Explizite Textfarbe: sonst macht Windows-Dunkelmodus weisse Schrift auf weiss.
FINECUT_STYLE = """
QDialog, QFrame#Side { background: #f4f4f4; color: #111111; }
QFrame#Side { border-left: 1px solid #d0d0d0; }
QLabel { color: #111111; }
QCheckBox, QRadioButton { color: #111111; spacing: 8px; }
QGroupBox { color: #111111; border: 1px solid #d0d0d0; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { color: #111111; subcontrol-origin: margin; left: 8px; }
QComboBox, QSpinBox, QDoubleSpinBox {
    color: #111111; background: #ffffff; border: 1px solid #b8b8b8;
    border-radius: 4px; padding: 2px 6px; min-height: 24px;
}
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: #9a9a9a; background: #f0f0f0; border: 1px solid #d4d4d4;
}
QComboBox QAbstractItemView {
    color: #111111; background: #ffffff;
    selection-background-color: #d7eadc; selection-color: #111111;
}
QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px; background: #ffffff; border: 1px solid #8a8a8a;
    border-radius: 3px;
}
QCheckBox::indicator:checked { background: #2d7d46; border: 1px solid #24663a; }
QRadioButton::indicator {
    width: 16px; height: 16px; background: #ffffff; border: 1px solid #8a8a8a; border-radius: 8px;
}
QRadioButton::indicator:checked { background: #2d7d46; border: 1px solid #24663a; }
QPushButton {
    color: #111111; background: #ffffff; border: 1px solid #b0b0b0;
    border-radius: 4px; padding: 6px 12px; min-height: 26px;
}
QPushButton#Seg {
    background: #e7e7e7; border: 1px solid #cfcfcf; border-bottom: none;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
    border-bottom-left-radius: 0; border-bottom-right-radius: 0;
    padding: 7px 16px; min-width: 118px; min-height: 18px; font-weight: 500;
}
QPushButton#Seg:checked {
    background: #ffffff; color: #111111; font-weight: 600;
}
QPushButton#Seg:hover { background: #f7f7f7; }
QPushButton:hover { background: #f0f0f0; }
QPushButton#Primary {
    background: #2d7d46; color: #ffffff; border: 1px solid #24663a; font-weight: bold;
}
QPushButton#Primary:hover { background: #338a4e; }
QTabBar::tab {
    color: #111111; background: #e4e4e4; border: 1px solid #c8c8c8;
    padding: 6px 16px; margin-right: 2px;
}
QTabBar::tab:selected { background: #ffffff; font-weight: 600; }
QScrollArea, QScrollArea > QWidget > QWidget { background: #f4f4f4; border: none; }
"""
