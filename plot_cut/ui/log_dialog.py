"""Protokollfenster: was gesendet wurde und was nicht."""

from __future__ import annotations

from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from .. import i18n
from .. import joblog
from .style import FINECUT_STYLE


class LogDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(FINECUT_STYLE)
        i18n.bind(self, window="Protokoll")
        self.resize(720, 520)

        root = QVBoxLayout(self)
        hint = QLabel()
        i18n.bind(
            hint,
            text="Einträge älter als 7 Tage werden gelöscht. Unten steht der Befehlsstrom, der rausgegangen ist.",
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.view.setFont(font)
        root.addWidget(self.view, 1)

        root.addWidget(QLabel(str(joblog.log_dir())))

        row = QHBoxLayout()
        row.addStretch(1)
        refresh = QPushButton()
        i18n.bind(refresh, text="Aktualisieren")
        refresh.clicked.connect(self.reload)
        close = QPushButton()
        i18n.bind(close, text="Schliessen")
        close.clicked.connect(self.accept)
        row.addWidget(refresh)
        row.addWidget(close)
        root.addLayout(row)
        self.reload()

    def reload(self) -> None:
        text = joblog.read_text().strip()
        self.view.setPlainText(text or i18n.tr("Noch kein Eintrag."))
        self.view.moveCursor(QTextCursor.MoveOperation.End)
