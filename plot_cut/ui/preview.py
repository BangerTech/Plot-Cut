"""Vorschau-Widget fuer Folie und Schneidpfade (mm-basiert).

Zwei Darstellungen:
- ``mode="plot"``     : Folie mit den Pfaden in echter Lage (zum Positionieren).
- ``mode="plot_out"`` : FineCut-Stil mit Richtungsfarben (schwarz CCW, rot CW),
                        gelben Leerfahrten, Reihenfolge-Nummern, optionalen
                        Pfeilen und gruener Kopfposition fuer die Simulation.

Bedienung: Mausrad zoomt um den Mauszeiger, Ziehen verschiebt, Doppelklick
passt wieder auf das Objekt ein.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPolygonF, QWheelEvent
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ..geometry import Polyline

MIN_SCALE = 0.05  # px pro mm
MAX_SCALE = 200.0

# Helle Folie mit dunklen Schnittlinien, wie in FineCut.
OFF_SHEET = "#3a3a3a"
SHEET = "#f5f5f2"
GRID_LIGHT = "#e6e6e2"
GRID_STRONG = "#d2d2cc"
SHEET_EDGE = "#8a8a84"
CUT_CCW = "#111111"
CUT_CW = "#d02828"
TRAVEL = "#d49a00"
ORDER = "#1f6fd1"
ORIGIN = "#1f9d3a"
DIMENSION = "#1f6fd1"


class PreviewWidget(QWidget):
    def __init__(self, mode: str = "plot") -> None:
        super().__init__()
        self.mode = mode
        self.polylines: list[Polyline] = []
        self.sheet_width_mm: float = 610.0

        # Plot-Out-Optionen
        self.show_arrows = False
        self.show_order = True
        self.show_travel = True

        # Simulation
        self.sim_progress: float = 1.0
        self._total_len = 0.0

        # Ansicht: Bildschirm = (mm - center) * scale + Widgetmitte, y gespiegelt
        self._scale = 1.0
        self._center = QPointF(0.0, 0.0)
        self._fit_pending = True
        self._drag_from: QPointF | None = None

        self.setMinimumSize(360, 260)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)

    # -- Daten -------------------------------------------------------------

    def set_data(self, polylines: list[Polyline], sheet_width_mm: float, refit: bool = True) -> None:
        self.polylines = polylines
        self.sheet_width_mm = max(sheet_width_mm, 1.0)
        self._total_len = sum(pl.length() for pl in polylines)
        if refit:
            self._fit_pending = True
        self.update()

    def set_options(self, *, arrows: bool, order: bool, travel: bool) -> None:
        self.show_arrows = arrows
        self.show_order = order
        self.show_travel = travel
        self.update()

    def set_sim_progress(self, value: float) -> None:
        self.sim_progress = max(0.0, min(1.0, value))
        self.update()

    # -- Ansicht -----------------------------------------------------------

    def fit_content(self) -> None:
        """Passt die Ansicht auf die Pfade ein (plus Rand und Ursprung)."""
        minx, miny, maxx, maxy = _bounds(self.polylines)
        minx, miny = min(minx, 0.0), min(miny, 0.0)
        pad = max(10.0, 0.15 * max(maxx - minx, maxy - miny))
        self._fit_rect(minx - pad, miny - pad, maxx + pad, maxy + pad)

    def fit_sheet(self) -> None:
        """Zeigt die ganze Folienbreite."""
        _, _, _, maxy = _bounds(self.polylines)
        height = max(maxy, self.sheet_width_mm * 0.4)
        self._fit_rect(-10.0, -10.0, self.sheet_width_mm + 10.0, height + 10.0)

    def _fit_rect(self, x0: float, y0: float, x1: float, y1: float) -> None:
        w = max(x1 - x0, 1.0)
        h = max(y1 - y0, 1.0)
        self._scale = _clamp(min(self.width() / w, self.height() / h), MIN_SCALE, MAX_SCALE)
        self._center = QPointF((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        self._fit_pending = False
        self.update()

    def _to_px(self, x_mm: float, y_mm: float) -> QPointF:
        return QPointF(
            self.width() / 2.0 + (x_mm - self._center.x()) * self._scale,
            self.height() / 2.0 - (y_mm - self._center.y()) * self._scale,
        )

    def _to_mm(self, p: QPointF) -> QPointF:
        return QPointF(
            self._center.x() + (p.x() - self.width() / 2.0) / self._scale,
            self._center.y() - (p.y() - self.height() / 2.0) / self._scale,
        )

    # -- Maus --------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        anchor = event.position()
        before = self._to_mm(anchor)
        factor = 1.25 if event.angleDelta().y() > 0 else 1 / 1.25
        self._scale = _clamp(self._scale * factor, MIN_SCALE, MAX_SCALE)
        after = self._to_mm(anchor)
        self._center += before - after
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._drag_from = event.position()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_from is None:
            return
        delta = event.position() - self._drag_from
        self._drag_from = event.position()
        self._center -= QPointF(delta.x() / self._scale, -delta.y() / self._scale)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: ARG002
        self._drag_from = None
        self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: ARG002
        self.fit_content()

    def resizeEvent(self, event) -> None:  # noqa: ARG002
        if self._fit_pending:
            self.fit_content()

    # -- Zeichnen ----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: ARG002
        if self._fit_pending:
            self.fit_content()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(OFF_SHEET))

        self._paint_sheet(p)
        if not self.polylines:
            p.setPen(QColor("#888"))
            p.drawText(self.rect(), Qt.AlignCenter, "Keine Auswahl")
            p.end()
            return

        if self.mode == "plot":
            self._paint_plot(p)
        else:
            self._paint_plot_out(p)
        self._paint_dimensions(p)
        self._paint_hint(p)
        p.end()

    def _paint_sheet(self, p: QPainter) -> None:
        # Die Folie ist eine Rolle: Breite fest, Laenge (y) nach oben unbegrenzt.
        top_mm = self._to_mm(QPointF(0, 0)).y() + 1.0
        tl = self._to_px(0.0, max(top_mm, 1.0))
        br = self._to_px(self.sheet_width_mm, 0.0)
        sheet = QRectF(tl, br).normalized()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(SHEET))
        p.drawRect(sheet)

        self._paint_grid(p, sheet)

        p.setPen(QPen(QColor(SHEET_EDGE), 1.0, Qt.DashLine))
        p.drawLine(self._to_px(0, 0), self._to_px(0, top_mm))
        p.drawLine(self._to_px(self.sheet_width_mm, 0), self._to_px(self.sheet_width_mm, top_mm))
        p.drawLine(self._to_px(0, 0), self._to_px(self.sheet_width_mm, 0))

        # Ursprung (Startpunkt des Messers)
        origin = self._to_px(0, 0)
        p.setPen(QPen(QColor(ORIGIN), 1.6))
        p.drawLine(origin, origin + QPointF(14, 0))
        p.drawLine(origin, origin + QPointF(0, -14))
        p.setFont(_font(8))
        p.drawText(origin + QPointF(4, 14), "0,0")

    def _paint_grid(self, p: QPainter, sheet: QRectF) -> None:
        step = 10.0
        while step * self._scale < 12:
            step *= 5 if str(int(step))[0] == "1" else 2
        p.save()
        p.setClipRect(sheet)
        x0 = self._to_mm(sheet.topLeft()).x()
        x1 = self._to_mm(sheet.bottomRight()).x()
        y1 = self._to_mm(sheet.topLeft()).y()
        y0 = self._to_mm(sheet.bottomRight()).y()
        light = QPen(QColor(GRID_LIGHT), 1)
        strong = QPen(QColor(GRID_STRONG), 1)
        k = math.floor(x0 / step)
        while k * step <= x1:
            p.setPen(strong if k % 5 == 0 else light)
            p.drawLine(self._to_px(k * step, y0), self._to_px(k * step, y1))
            k += 1
        k = math.floor(y0 / step)
        while k * step <= y1:
            p.setPen(strong if k % 5 == 0 else light)
            p.drawLine(self._to_px(x0, k * step), self._to_px(x1, k * step))
            k += 1
        p.restore()

    def _paint_plot(self, p: QPainter) -> None:
        # Blasse Originalfarbe zeigt, was gezeichnet wurde; die schwarze Kontur ist der Schnitt.
        for pl in self.polylines:
            if pl.closed and pl.color.startswith("#"):
                fill = QColor(pl.color)
                fill.setAlpha(45)
                p.setPen(Qt.NoPen)
                p.setBrush(fill)
                p.drawPolygon(self._poly(pl))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(CUT_CCW), 1.6))
        for pl in self.polylines:
            p.drawPolyline(self._poly(pl))

    def _paint_plot_out(self, p: QPainter) -> None:
        drawn = 0.0
        limit = self.sim_progress * self._total_len
        prev_end: QPointF | None = None

        ccw_pen = QPen(QColor(CUT_CCW), 1.6)
        cw_pen = QPen(QColor(CUT_CW), 1.6)
        travel_pen = QPen(QColor(TRAVEL), 1.2, Qt.DashLine)
        head_point: QPointF | None = None

        for idx, pl in enumerate(self.polylines):
            start_px = self._to_px(*pl.points[0])
            if self.show_travel and prev_end is not None:
                p.setPen(travel_pen)
                p.drawLine(prev_end, start_px)

            p.setPen(ccw_pen if (not pl.closed or pl.is_ccw()) else cw_pen)
            for a, b in zip(pl.points, pl.points[1:], strict=False):
                seg_len = math.hypot(b[0] - a[0], b[1] - a[1])
                a_px, b_px = self._to_px(*a), self._to_px(*b)
                if drawn + seg_len <= limit:
                    p.drawLine(a_px, b_px)
                    head_point = b_px
                elif drawn < limit:
                    t = (limit - drawn) / seg_len if seg_len > 0 else 0.0
                    mid = a_px + (b_px - a_px) * t
                    p.drawLine(a_px, mid)
                    head_point = mid
                drawn += seg_len

            if self.show_arrows and len(pl.points) >= 2:
                self._draw_arrow(p, pl.points)

            if self.show_order:
                p.setPen(QColor(ORDER))
                p.setFont(_font(8))
                p.drawText(start_px + QPointF(4, -4), str(idx + 1))

            # Startpunkt markieren
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ORDER))
            p.drawEllipse(start_px, 2.5, 2.5)
            p.setBrush(Qt.NoBrush)

            prev_end = self._to_px(*pl.points[-1])

        if self.sim_progress < 1.0 and head_point is not None:
            p.setPen(QPen(QColor(ORIGIN), 2))
            p.setBrush(QColor(ORIGIN))
            p.drawEllipse(head_point, 4, 4)
            p.setBrush(Qt.NoBrush)

    def _paint_dimensions(self, p: QPainter) -> None:
        minx, miny, maxx, maxy = _bounds(self.polylines)
        tl = self._to_px(minx, maxy)
        br = self._to_px(maxx, miny)
        box = QRectF(tl, br).normalized()
        p.setFont(_font(9))
        p.setPen(QColor(DIMENSION))
        label = f"{maxx - minx:.1f} x {maxy - miny:.1f} mm"
        p.drawText(QRectF(box.right() - 200, box.bottom() + 4, 200, 16),
                   Qt.AlignRight | Qt.AlignTop, label)

    def _paint_hint(self, p: QPainter) -> None:
        p.setFont(_font(8))
        p.setPen(QColor("#9a9a9a"))
        p.drawText(
            QRectF(8, self.height() - 20, self.width() - 16, 16),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"Folie {self.sheet_width_mm:.0f} mm  |  Mausrad: Zoom  |  Ziehen: verschieben  "
            "|  Doppelklick: einpassen",
        )

    def _draw_arrow(self, p: QPainter, pts) -> None:
        a_px, b_px = self._to_px(*pts[-2]), self._to_px(*pts[-1])
        ang = math.atan2(b_px.y() - a_px.y(), b_px.x() - a_px.x())
        size = 7.0
        left = QPointF(b_px.x() - size * math.cos(ang - math.pi / 6),
                       b_px.y() - size * math.sin(ang - math.pi / 6))
        right = QPointF(b_px.x() - size * math.cos(ang + math.pi / 6),
                        b_px.y() - size * math.sin(ang + math.pi / 6))
        p.setBrush(p.pen().color())
        p.drawPolygon(QPolygonF([b_px, left, right]))
        p.setBrush(Qt.NoBrush)

    def _poly(self, pl: Polyline) -> QPolygonF:
        return QPolygonF([self._to_px(x, y) for (x, y) in pl.points])


def view_buttons(preview: PreviewWidget) -> QHBoxLayout:
    """Knoepfe "Einpassen" und "Ganze Folie" fuer eine Vorschau."""
    row = QHBoxLayout()
    fit = QPushButton("Einpassen")
    fit.setToolTip("Auf das Objekt zoomen (auch Doppelklick in die Vorschau)")
    fit.clicked.connect(preview.fit_content)
    row.addWidget(fit)
    sheet = QPushButton("Ganze Folie")
    sheet.setToolTip("Gesamte Folienbreite anzeigen")
    sheet.clicked.connect(preview.fit_sheet)
    row.addWidget(sheet)
    return row


def _font(size: int) -> QFont:
    f = QFont()
    f.setPointSize(size)
    return f


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _bounds(polylines: list[Polyline]) -> tuple[float, float, float, float]:
    if not polylines:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [x for pl in polylines for x, _ in pl.points]
    ys = [y for pl in polylines for _, y in pl.points]
    return (min(xs), min(ys), max(xs), max(ys))
