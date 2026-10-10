"""Einfache, selbst gezeichnete Icons (keine Mimaki-Originalgrafiken)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF


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
