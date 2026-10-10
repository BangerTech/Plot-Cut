"""Einfache, selbst gezeichnete Icons (keine Mimaki-Originalgrafiken)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)


def _base_pixmap(size: int = 28) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    return pm


def _painter(pm: QPixmap) -> QPainter:
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor("#e6e6e6"))
    pen.setWidthF(1.6)
    p.setPen(pen)
    return p


def icon_plot(size: int = 28) -> QIcon:
    pm = _base_pixmap(size)
    p = _painter(pm)
    p.drawRect(5, 6, 18, 12)
    # "Blatt" mit Pfeil nach rechts (Ausgabe)
    arrow = QPolygonF([QPointF(10, 12), QPointF(18, 12), QPointF(18, 9), QPointF(23, 14),
                       QPointF(18, 19), QPointF(18, 16), QPointF(10, 16)])
    p.setBrush(QColor("#4fa3ff"))
    p.drawPolygon(arrow)
    p.end()
    return QIcon(pm)


def icon_setup(size: int = 28) -> QIcon:
    pm = _base_pixmap(size)
    p = _painter(pm)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(9, 9, 10, 10))
    for ang in range(0, 360, 45):
        p.save()
        p.translate(14, 14)
        p.rotate(ang)
        p.drawLine(0, 7, 0, 10)
        p.restore()
    p.end()
    return QIcon(pm)


def icon_info(size: int = 28) -> QIcon:
    pm = _base_pixmap(size)
    p = _painter(pm)
    p.drawEllipse(QRectF(6, 6, 16, 16))
    f = QFont()
    f.setBold(True)
    f.setPointSize(10)
    p.setFont(f)
    p.drawText(QRectF(6, 5, 16, 18), Qt.AlignCenter, "i")
    p.end()
    return QIcon(pm)


def icon_test(size: int = 28) -> QIcon:
    pm = _base_pixmap(size)
    p = _painter(pm)
    # Stecker/Verbindung
    p.drawLine(5, 14, 12, 14)
    p.drawRect(12, 10, 8, 8)
    p.drawLine(20, 12, 24, 12)
    p.drawLine(20, 16, 24, 16)
    p.end()
    return QIcon(pm)


def icon_generic(letter: str, size: int = 28) -> QIcon:
    pm = _base_pixmap(size)
    p = _painter(pm)
    p.drawRoundedRect(QRectF(5, 5, 18, 18), 3, 3)
    f = QFont()
    f.setBold(True)
    f.setPointSize(9)
    p.setFont(f)
    p.drawText(QRectF(5, 5, 18, 18), Qt.AlignCenter, letter)
    p.end()
    return QIcon(pm)


def _arrow_head(p: QPainter, tip: QPointF, angle_deg: float, length: float, color: QColor) -> None:
    a = math.radians(angle_deg)
    left = QPointF(tip.x() - length * math.cos(a - 0.5), tip.y() - length * math.sin(a - 0.5))
    right = QPointF(tip.x() - length * math.cos(a + 0.5), tip.y() - length * math.sin(a + 0.5))
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPolygon(QPolygonF([tip, left, right]))


def _arc_arrows(p: QPainter, c: float, r: float, color: QColor, pen_w: float, two: bool) -> None:
    rect = QRectF(c - r, c - r, 2 * r, 2 * r)
    pen = QPen(color, pen_w, Qt.SolidLine, Qt.FlatCap)
    spans = [(30, 150), (210, 150)] if two else [(60, 290)]
    for start, span in spans:
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawArc(rect, int(start * 16), int(span * 16))
        end = math.radians(start + span)
        tip = QPointF(c + r * math.cos(end), c - r * math.sin(end))
        heading = -(start + span + 90)
        _arrow_head(p, tip, heading, pen_w * 2.2, color)


def round_icon(name: str, size: int = 48) -> QIcon:
    """Runde Knopf-Icons fuer Plot/Ausplotten (eigene Zeichnung im FineCut-Stil)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    c = size / 2.0
    ring = QRectF(2, 2, size - 4, size - 4)

    if name == "cut":
        grad = QLinearGradient(0, 0, 0, size)
        grad.setColorAt(0.0, QColor("#ffffff"))
        grad.setColorAt(1.0, QColor("#c9c9c9"))
        p.setPen(QPen(QColor("#8a8a8a"), 1.2))
        p.setBrush(grad)
        p.drawEllipse(ring)
        p.setBrush(QColor("#d32f2f"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(6, 6, size - 12, size - 12))
        p.setBrush(QColor("#ffffff"))
        s = size / 48.0
        p.drawRect(QRectF(15 * s, 14 * s, 18 * s, 7 * s))
        p.drawRect(QRectF(19 * s, 21 * s, 10 * s, 6 * s))
        p.drawPolygon(QPolygonF([QPointF(21 * s, 27 * s), QPointF(27 * s, 27 * s), QPointF(24 * s, 35 * s)]))
        p.end()
        return QIcon(pm)

    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0.0, QColor("#ffffff"))
    grad.setColorAt(1.0, QColor("#d6d6d6"))
    p.setPen(QPen(QColor("#9a9a9a"), 1.2))
    p.setBrush(grad)
    p.drawEllipse(ring)

    green = QColor("#2e9e3e")
    blue = QColor("#2f6fd1")
    orange = QColor("#ef8a17")
    dark = QColor("#202020")
    r = size * 0.27
    w = size * 0.085

    if name == "init":
        _arc_arrows(p, c, r, green, w, two=True)
    elif name == "original":
        _arc_arrows(p, c, r, orange, w, two=True)
    elif name == "rotate":
        _arc_arrows(p, c, r, green, w, two=False)
        f = QFont("Segoe UI")
        f.setPixelSize(int(size * 0.26))
        f.setBold(True)
        p.setFont(f)
        p.setPen(dark)
        p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "0")
    elif name == "sheet":
        pen = QPen(blue, w, Qt.SolidLine, Qt.FlatCap)
        for dy, direction in ((-size * 0.1, 1), (size * 0.1, -1)):
            y = c + dy
            x0, x1 = c - r, c + r
            p.setPen(pen)
            p.drawLine(QPointF(x0 + w, y), QPointF(x1 - w, y))
            tip = QPointF(x1, y) if direction > 0 else QPointF(x0, y)
            _arrow_head(p, tip, 0 if direction > 0 else 180, w * 2.4, blue)
    elif name == "quit":
        path = QPainterPath()
        path.moveTo(c + r * 0.8, c - r * 0.9)
        path.lineTo(c + r * 0.8, c + r * 0.1)
        path.lineTo(c - r * 0.5, c + r * 0.1)
        p.setPen(QPen(dark, w, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        _arrow_head(p, QPointF(c - r * 0.95, c + r * 0.1), 180, w * 2.6, dark)
    elif name == "fit":
        p.setPen(QPen(blue, 1.6))
        p.setBrush(QColor("#d9e6fb"))
        p.drawRect(QRectF(c - r * 0.55, c - r * 0.55, r * 1.1, r * 1.1))
        for ang in (0, 90, 180, 270):
            a = math.radians(ang)
            tip = QPointF(c + r * 1.05 * math.cos(a), c - r * 1.05 * math.sin(a))
            p.setPen(QPen(blue, w * 0.7))
            p.drawLine(QPointF(c + r * 0.55 * math.cos(a), c - r * 0.55 * math.sin(a)), tip)
            _arrow_head(p, tip, -ang, w * 1.8, blue)
    elif name == "move":
        p.setPen(Qt.NoPen)
        p.setBrush(dark)
        step = r * 0.75
        for iy in (-1, 0, 1):
            for ix in (-1, 0, 1):
                cx, cy = c + ix * step, c + iy * step
                if ix == 0 and iy == 0:
                    p.drawEllipse(QPointF(cx, cy), w * 0.6, w * 0.6)
                    continue
                ang = math.degrees(math.atan2(iy, ix))
                _arrow_head(p, QPointF(cx + ix * w * 0.4, cy + iy * w * 0.4), ang, w * 1.6, dark)
    p.end()
    return QIcon(pm)


def logo_path() -> Path:
    """Logo neben dem Quelltext oder im gepackten Programm."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / "logo.png"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2] / "assets" / "logo.png"


def app_icon() -> QIcon:
    path = logo_path()
    if path.is_file():
        return QIcon(str(path))
    return icon_wordmark()


def icon_wordmark(size: int = 28) -> QIcon:
    """Kleines Plot-Cut-Wortzeichen (kein Hersteller-Logo)."""
    pm = _base_pixmap(size)
    p = _painter(pm)
    p.setBrush(QColor("#c0392b"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(2, 7, 24, 14), 3, 3)
    f = QFont()
    f.setBold(True)
    f.setPointSize(8)
    p.setPen(QColor("#ffffff"))
    p.setFont(f)
    p.drawText(QRectF(2, 7, 24, 14), Qt.AlignCenter, "PC")
    p.end()
    return QIcon(pm)
