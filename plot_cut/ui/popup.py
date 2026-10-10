"""Hinweisfenster, die vor dem immer-oben-Panel bleiben und den Text umbrechen."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

_STYLE = """
QDialog { background: #f4f4f4; }
QLabel { color: #111111; background: transparent; }
QPushButton {
    color: #111111; background: #ffffff; border: 1px solid #b0b0b0;
    border-radius: 4px; padding: 6px 18px; min-width: 72px; min-height: 26px;
}
QPushButton:hover { background: #f0f0f0; }
"""

_ICONS = {
    "information": QStyle.StandardPixmap.SP_MessageBoxInformation,
    "warning": QStyle.StandardPixmap.SP_MessageBoxWarning,
    "critical": QStyle.StandardPixmap.SP_MessageBoxCritical,
    "question": QStyle.StandardPixmap.SP_MessageBoxQuestion,
}


def _show(
    parent: QWidget | None,
    kind: str,
    title: str,
    text: str,
    buttons: list[tuple[str, int]],
    default: int,
) -> int:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    dlg.setModal(True)
    dlg.setStyleSheet(_STYLE)

    root = QHBoxLayout(dlg)
    root.setContentsMargins(18, 16, 18, 16)
    root.setSpacing(14)

    icon = QLabel()
    icon.setPixmap(dlg.style().standardIcon(_ICONS[kind]).pixmap(32, 32))
    icon.setAlignment(Qt.AlignmentFlag.AlignTop)
    root.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

    col = QVBoxLayout()
    col.setSpacing(14)
    label = QLabel(text)
    label.setWordWrap(True)
    label.setFixedWidth(460)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    col.addWidget(label)

    row = QHBoxLayout()
    row.addStretch(1)
    result = {"code": default}

    def choose(code: int) -> None:
        result["code"] = code
        dlg.done(code)

    for caption, code in buttons:
        btn = QPushButton(caption)
        btn.clicked.connect(lambda _checked=False, code=code: choose(code))
        if code == default:
            btn.setDefault(True)
        row.addWidget(btn)
    col.addLayout(row)
    root.addLayout(col)

    dlg.raise_()
    dlg.activateWindow()
    dlg.exec()
    return result["code"]


def information(parent: QWidget | None, title: str, text: str) -> int:
    return _show(parent, "information", title, text, [("OK", 1)], 1)


def warning(parent: QWidget | None, title: str, text: str) -> int:
    return _show(parent, "warning", title, text, [("OK", 1)], 1)


def critical(parent: QWidget | None, title: str, text: str) -> int:
    return _show(parent, "critical", title, text, [("OK", 1)], 1)


def question(parent: QWidget | None, title: str, text: str) -> bool:
    return _show(parent, "question", title, text, [("Ja", 1), ("Nein", 0)], 0) == 1
