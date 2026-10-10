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

# FineCut-Plot: links vom Ursprung grau (Maschine), rechts weisse Folie.
OFF_SHEET = "#a3a3a3"
SHEET = "#ffffff"
RULER_BG = "#f3f3f3"
RULER_FG = "#666666"
RULER_H = 28
GRID_LIGHT = "#eeeeee"
GRID_STRONG = "#dddddd"
SHEET_EDGE = "#9a9a9a"
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
        self.sheet_height_mm: float = 1000.0
        self.cut_lines_only: bool = False
        # Mimaki/FineCut: Ursprung rechts unten, +X laeuft nach links in die Folie.
        self.origin_corner: str = "bottom_right"

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

    def set_data(
        self,
        polylines: list[Polyline],
        sheet_width_mm: float,
        refit: bool = True,
        sheet_height_mm: float | None = None,
    ) -> None:
        self.polylines = polylines
        self.sheet_width_mm = max(sheet_width_mm, 1.0)
        if sheet_height_mm is not None:
            self.sheet_height_mm = max(sheet_height_mm, 1.0)
        self._total_len = sum(pl.length() for pl in polylines)
        if refit:
            self._fit_pending = True
        self.update()

    def set_cut_lines(self, enabled: bool) -> None:
        """Schneidelinie: nur die Kontur, ohne gefuellte Flaeche."""
        self.cut_lines_only = enabled
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

    def fit_default(self) -> None:
        """Plot: ganze Folie (wie FineCut). Plot Out: auf die Pfade."""
        if self.mode == "plot":
            self.fit_sheet()
        else:
            self.fit_content()

    def fit_content(self) -> None:
        """Passt die Ansicht auf die Pfade ein (plus Rand und Ursprung)."""
        minx, miny, maxx, maxy = _bounds(self.polylines)
        minx, miny = min(minx, 0.0), min(miny, 0.0)
        pad = max(10.0, 0.15 * max(maxx - minx, maxy - miny, 1.0))
        self._fit_rect(minx - pad, miny - pad, maxx + pad, maxy + pad)

    def fit_sheet(self) -> None:
        """Ganze Folienbreite. Ursprung unten, y=0 auf dem Lineal.

        Mimaki/FineCut (``bottom_right``): Ursprung am rechten Rand, Folie nach
        links, links davon grau. Ohne Rahmen liegt das Objekt direkt am Ursprung.
        """
        if self.width() < 8 or self.height() < 8:
            self._fit_pending = True
            return
        sheet = max(self.sheet_width_mm, 1.0)
        if self.origin_corner == "bottom_right":
            # View-X: 0 = Ursprung rechts, negativ = in die Folie.
            x0, x1 = -sheet * 1.04, sheet * 0.012
        else:
            x0, x1 = -sheet * 0.012, sheet * 1.04
        self._scale = _clamp(self.width() / max(x1 - x0, 1.0), MIN_SCALE, MAX_SCALE)
        self._center = QPointF(
            (x0 + x1) / 2.0,
            (self.height() / 2.0 - RULER_H) / self._scale,
        )
        self._fit_pending = False
        self.update()

    def _fit_rect(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """``x``/``y`` sind Maschinen-Millimeter."""
        if self.width() < 8 or self.height() < 8:
            self._fit_pending = True
            return
        vx0, vx1 = self._view_x(x0), self._view_x(x1)
        if vx0 > vx1:
            vx0, vx1 = vx1, vx0
        w = max(vx1 - vx0, 1.0)
        h = max(y1 - y0, 1.0)
        self._scale = _clamp(min(self.width() / w, self.height() / h), MIN_SCALE, MAX_SCALE)
        self._center = QPointF((vx0 + vx1) / 2.0, (y0 + y1) / 2.0)
        self._fit_pending = False
        self.update()

    def _view_x(self, x_mm: float) -> float:
        """Maschinen-X nach View-X. Bei Mimaki waechst X nach links."""
        return -x_mm if self.origin_corner == "bottom_right" else x_mm

    def _machine_x(self, view_x: float) -> float:
        return -view_x if self.origin_corner == "bottom_right" else view_x

    def _to_view(self, p: QPointF) -> QPointF:
        return QPointF(
            self._center.x() + (p.x() - self.width() / 2.0) / self._scale,
            self._center.y() - (p.y() - self.height() / 2.0) / self._scale,
        )

    def _to_px(self, x_mm: float, y_mm: float) -> QPointF:
        return QPointF(
            self.width() / 2.0 + (self._view_x(x_mm) - self._center.x()) * self._scale,
            self.height() / 2.0 - (y_mm - self._center.y()) * self._scale,
        )

    def _to_mm(self, p: QPointF) -> QPointF:
        view = self._to_view(p)
        return QPointF(self._machine_x(view.x()), view.y())

    # -- Maus --------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        anchor = event.position()
        before = self._to_view(anchor)
        factor = 1.25 if event.angleDelta().y() > 0 else 1 / 1.25
        self._scale = _clamp(self._scale * factor, MIN_SCALE, MAX_SCALE)
        after = self._to_view(anchor)
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
        self.fit_default()

    def resizeEvent(self, event) -> None:
        old = event.oldSize()
        if self._fit_pending or old.width() < 8 or old.height() < 8:
            self.fit_default()

    # -- Zeichnen ----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: ARG002
        if self._fit_pending:
            self.fit_default()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(OFF_SHEET))

        self._paint_sheet(p)
        if not self.polylines:
            p.setPen(QColor("#666"))
            p.drawText(self.rect(), Qt.AlignCenter, "Keine Auswahl")
            p.end()
            return

        if self.mode == "plot":
            self._paint_plot(p)
        else:
            self._paint_plot_out(p)
            self._paint_dimensions(p)
        self._paint_origin(p)
        self._paint_ruler(p)
        p.end()

    def _paint_sheet(self, p: QPainter) -> None:
        # FineCut: links vom Ursprung grau (Maschine), rechts/oben weisse Folie.
        # Kein Karopapier im Plot-Modus.
        top_mm = min(self._to_mm(QPointF(0, 0)).y() + 1.0, self.sheet_height_mm)
        tl = self._to_px(0.0, max(top_mm, 0.0))
        br = self._to_px(self.sheet_width_mm, 0.0)
        sheet = QRectF(tl, br).normalized()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(SHEET))
        p.drawRect(sheet)

        if self.mode != "plot":
            self._paint_grid(p, sheet)

        p.setPen(QPen(QColor("#8e8e8e"), 1.0))
        p.drawLine(self._to_px(0, 0), self._to_px(0, self.sheet_height_mm))
        p.drawLine(self._to_px(0, 0), self._to_px(self.sheet_width_mm, 0))
        p.drawLine(
            self._to_px(0, self.sheet_height_mm),
            self._to_px(self.sheet_width_mm, self.sheet_height_mm),
        )

    def _paint_grid(self, p: QPainter, sheet: QRectF) -> None:
        step = 10.0
        while step * self._scale < 12:
            step *= 5 if str(int(step))[0] == "1" else 2
        p.save()
        p.setClipRect(sheet)
        xa = self._to_mm(sheet.topLeft()).x()
        xb = self._to_mm(sheet.bottomRight()).x()
        x0, x1 = min(xa, xb), max(xa, xb)
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
        # Wie FineCut: gefuelltes Objekt auf der weissen Folie.
        for pl in self.polylines:
            color = QColor(pl.color if pl.color.startswith("#") else "#111111")
            if self.cut_lines_only or pl.kind == "frame":
                # Rahmen und Schneidelinie: nur die Linie, die der Plotter faehrt.
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(color, 1.4))
                if pl.closed:
                    p.drawPolygon(self._poly(pl))
                else:
                    p.drawPolyline(self._poly(pl))
                continue
            if pl.closed:
                p.setPen(QPen(color, 1.0))
                p.setBrush(color)
                p.drawPolygon(self._poly(pl))
            else:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(color, 1.6))
                p.drawPolyline(self._poly(pl))
        p.setBrush(Qt.NoBrush)

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
        p.setFont(_font(11))
        p.setPen(QColor(DIMENSION))
        label = f"{maxx - minx:.1f} x {maxy - miny:.1f} mm"
        # Neben das Objekt, auf die Folie — nicht unters Lineal.
        anchor = box.left() if self.origin_corner == "bottom_right" else box.right()
        rect = QRectF(anchor - 150, box.top() - 18, 140, 16)
        if self.origin_corner != "bottom_right":
            rect = QRectF(anchor + 6, box.top() - 18, 140, 16)
        p.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, label)

    def _paint_origin(self, p: QPainter) -> None:
        """Gruene Ursprungsmarke. Bei Mimaki sitzt sie rechts unten."""
        o = self._to_px(0.0, 0.0)
        p.setPen(QPen(QColor(ORIGIN), 2))
        outward = 18 if self.origin_corner == "bottom_right" else -18
        p.drawLine(o, o + QPointF(outward, 0))
        p.drawLine(o, o + QPointF(0, -18))
        p.setFont(_font(8))
        p.drawText(o + QPointF(4 if outward > 0 else -16, 14), "0")

    def _paint_ruler(self, p: QPainter) -> None:
        """Millimeter-Lineal am unteren Rand, wie FineCut."""
        y = self.height() - RULER_H
        bar = QRectF(0, y, self.width(), RULER_H)
        p.fillRect(bar, QColor(RULER_BG))
        p.setPen(QPen(QColor("#c8c8c8"), 1))
        p.drawLine(0, y, self.width(), y)

        a = self._to_mm(QPointF(0, y)).x()
        b = self._to_mm(QPointF(self.width(), y)).x()
        lo, hi = min(a, b), max(a, b)
        step = 10.0
        while step * self._scale < 8:
            step *= 5 if str(int(step))[0] == "1" else 2
        p.setFont(_font(7))
        p.setPen(QColor(RULER_FG))
        k = math.floor(lo / step)
        while k * step <= hi:
            mm = k * step
            x = self._to_px(mm, 0).x()
            major = abs(k) % 5 == 0
            tick = 12 if major else 6
            p.drawLine(QPointF(x, y + 1), QPointF(x, y + tick))
            if major:
                p.drawText(QRectF(x - 18, y + 8, 36, 12), Qt.AlignHCenter | Qt.AlignTop, f"{mm:.0f}")
            k += 1

    def _paint_hint(self, p: QPainter) -> None:
        p.setFont(_font(8))
        p.setPen(QColor("#9a9a9a"))
        p.drawText(
            QRectF(8, self.height() - 20, self.width() - 16, 16),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"Folie {self.sheet_width_mm:.0f} mm  |  Mausrad: Zoom  |  Ziehen: verschieben  "
            "|  Doppelklick: ganze Folie",
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
    btn_style = (
        "QPushButton { color: #111111; background: #ffffff; "
        "border: 1px solid #b0b0b0; padding: 6px 10px; }"
    )
    fit = QPushButton("Einpassen")
    fit.setStyleSheet(btn_style)
    fit.setToolTip("Auf das Objekt zoomen (auch Doppelklick in die Vorschau)")
    fit.clicked.connect(preview.fit_content)
    row.addWidget(fit)
    sheet = QPushButton("Ganze Folie")
    sheet.setStyleSheet(btn_style)
    sheet.setToolTip("Gesamte Folienbreite anzeigen")
    sheet.clicked.connect(preview.fit_sheet)
    row.addWidget(sheet)
    return row


def _font(size: int) -> QFont:
    f = QFont("Segoe UI")
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
