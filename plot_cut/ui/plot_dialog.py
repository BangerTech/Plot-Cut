"""[Plot]-Fenster im FineCut-Look: Vorschau/Schneidelinie links, rechts die
Werkzeugleiste mit Blatt, Offset, Groesse, Kopien, Rahmen, Layout und Farben."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import geometry as g
from .icons import round_icon
from .popup import critical
from .preview import PreviewWidget
from .style import FINECUT_STYLE, ComboBox

if TYPE_CHECKING:
    from ..app import AppController

H_ARROW = "↔"
V_ARROW = "↕"

_SIDE_STYLE = """
QFrame#Table { background: #ffffff; border: 1px solid #c8c8c8; }
QFrame#Table QLabel { background: transparent; }
QFrame#Rule { background: #d6d6d6; max-height: 1px; min-height: 1px; border: none; }
QLabel#Arrow { color: #333333; font-size: 15px; }
QLabel#Link { color: #111111; font-size: 16px; font-weight: bold; }
QLabel#Total { color: #111111; font-weight: 600; }
QToolButton#Round {
    color: #111111; background: transparent; border: 1px solid transparent;
    border-radius: 6px; padding: 2px 4px; font-size: 12px;
}
QToolButton#Round:hover { background: #e6eef9; border: 1px solid #b9cbe8; }
QToolButton#Round:pressed { background: #d4e2f6; }
QTabWidget::pane { border: 1px solid #c8c8c8; background: #ffffff; top: -1px; }
QTabWidget > QWidget { background: #ffffff; }
QTabBar::tab { padding: 5px 12px; }
QListWidget { color: #111111; background: #ffffff; border: none; }
QListWidget::item { padding: 3px 2px; border-bottom: 1px solid #222222; }
QListWidget::item:selected { background: #d7eadc; color: #111111; }
"""


class PlotDialog(QDialog):
    def __init__(
        self,
        controller: AppController,
        polylines: list[g.Polyline],
        document_path: str | None,
    ) -> None:
        super().__init__(None)
        self.controller = controller
        self.source = polylines
        self.document_path = document_path
        self._block = False
        self._user_scaled = False
        self._nat_w = 1.0
        self._nat_h = 1.0
        self._tab = 0

        self.setWindowTitle(f"Plot - {controller.profile_name}")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(FINECUT_STYLE + _SIDE_STYLE)
        self.resize(1240, 860)
        self.setMinimumSize(1020, 680)

        per_file = controller.per_file_settings(document_path)
        self._anchor = tuple(per_file.get("anchor", (0.0, 0.0)))  # Maschinen-Anteil X/Y

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_preview_side(), 1)

        side = QFrame()
        side.setObjectName("Side")
        side.setFixedWidth(450)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        host = QWidget()
        sl = QVBoxLayout(host)
        sl.setContentsMargins(12, 10, 12, 12)
        sl.setSpacing(10)
        scroll.setWidget(host)
        side_lay.addWidget(scroll)
        root.addWidget(side)

        sl.addLayout(self._build_top_buttons())
        sl.addWidget(self._build_table(per_file))
        sl.addWidget(self._build_layout_tabs(per_file))
        sl.addWidget(self._build_color_tabs(per_file), 1)

        linked = "" if self.distort.isChecked() else "—"
        self.link_size.setText(linked)
        self.link_scale.setText(linked)
        self._sync_size_from_source()
        self._apply_fixed_origin()

    # -- Aufbau ------------------------------------------------------------

    def _build_preview_side(self) -> QWidget:
        left = QWidget()
        lay = QVBoxLayout(left)
        lay.setContentsMargins(8, 8, 0, 0)
        lay.setSpacing(0)
        tabs = QHBoxLayout()
        tabs.setSpacing(0)
        self.tab_preview = QPushButton("Vorschau")
        self.tab_lines = QPushButton("Schneidelinie")
        for btn, index in ((self.tab_preview, 0), (self.tab_lines, 1)):
            btn.setObjectName("Seg")
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _checked=False, i=index: self._on_tab(i))
        self.tab_preview.setChecked(True)
        tabs.addWidget(self.tab_preview)
        tabs.addWidget(self.tab_lines)
        tabs.addStretch(1)
        lay.addLayout(tabs)
        self.preview = PreviewWidget(mode="plot")
        lay.addWidget(self.preview, 1)
        return left

    def _round_button(self, name: str, text: str, tip: str, handler, icon_px: int = 44) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("Round")
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setIcon(round_icon(name, icon_px + 8))
        btn.setIconSize(QSize(icon_px, icon_px))
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(handler)
        return btn

    def _build_top_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(2)
        row.addWidget(self._round_button(
            "init", "Initialisieren", "Alle Einstellungen dieses Fensters zurücksetzen", self._initialize))
        row.addWidget(self._round_button(
            "sheet", "Blattgröße einlesen",
            "Folienbreite und -länge aus dem Plotter-Profil übernehmen", self._read_sheet_size))
        row.addWidget(self._round_button("cut", "Schneiden...", "Weiter zum Ausplotten", self._open_plot_out, 50))
        row.addWidget(self._round_button("quit", "Beenden", "Fenster schließen", self.reject))
        return row

    def _mm(self, lo: float, hi: float, value: float, suffix: str = " mm", decimals: int = 1) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(lo, hi)
        box.setDecimals(decimals)
        box.setSuffix(suffix)
        box.setValue(value)
        box.setAlignment(Qt.AlignRight)
        box.setMinimumWidth(118)
        return box

    def _arrow(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("Arrow")
        lab.setAlignment(Qt.AlignCenter)
        lab.setFixedWidth(18)
        return lab

    def _rule(self) -> QFrame:
        line = QFrame()
        line.setObjectName("Rule")
        return line

    def _build_table(self, per_file: dict) -> QFrame:
        plotter = self.controller.profile["plotter"]
        table = QFrame()
        table.setObjectName("Table")
        grid = QGridLayout(table)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(5, 2)
        self._grid_row = 0

        def add_row(label: QWidget | str, left: QWidget | None, right: QWidget | None, link: QWidget | None = None) -> None:
            r = self._grid_row
            grid.addWidget(QLabel(label) if isinstance(label, str) else label, r, 0)
            if left is not None:
                grid.addWidget(self._arrow(H_ARROW), r, 1)
                grid.addWidget(left, r, 2)
            if link is not None:
                grid.addWidget(link, r, 3)
            if right is not None:
                grid.addWidget(self._arrow(V_ARROW), r, 4)
                grid.addWidget(right, r, 5)
            self._grid_row += 1

        def add_rule() -> None:
            grid.addWidget(self._rule(), self._grid_row, 0, 1, 6)
            self._grid_row += 1

        self.sheet_width = self._mm(10, 5000, float(plotter.get("sheet_width_mm", 610)))
        self.sheet_height = self._mm(10, 100000, float(plotter.get("sheet_height_mm", 1000)))
        self.sheet_width.valueChanged.connect(lambda: self._refresh(refit=True))
        self.sheet_height.valueChanged.connect(lambda: self._refresh(refit=False))
        add_row("Blattgröße", self.sheet_width, self.sheet_height)

        self.offset_x = self._mm(-5000, 5000, float(per_file.get("offset_x", 0)))
        self.offset_y = self._mm(-100000, 100000, float(per_file.get("offset_y", 0)))
        self.offset_x.valueChanged.connect(lambda: self._refresh(refit=False))
        self.offset_y.valueChanged.connect(lambda: self._refresh(refit=False))
        add_row("Offset", self.offset_x, self.offset_y)

        self.size_w = self._mm(0.1, 50000, 10)
        self.size_h = self._mm(0.1, 50000, 10)
        self.size_w.valueChanged.connect(self._on_width)
        self.size_h.valueChanged.connect(self._on_height)
        self.link_size = self._link_label()
        add_row("Größe", self.size_w, self.size_h, self.link_size)

        self.scale_x = self._mm(0.1, 10000, 100, suffix="", decimals=1)
        self.scale_y = self._mm(0.1, 10000, 100, suffix="", decimals=1)
        self.scale_x.valueChanged.connect(self._on_scale_x)
        self.scale_y.valueChanged.connect(self._on_scale_y)
        self.link_scale = self._link_label()
        add_row("Skalierung(%)", self.scale_x, self.scale_y, self.link_scale)
        add_rule()

        copies_x, copies_y = self._saved_copies(per_file)
        self.copies_x = QSpinBox()
        self.copies_y = QSpinBox()
        for box, value in ((self.copies_x, copies_x), (self.copies_y, copies_y)):
            box.setRange(1, 999)
            box.setValue(value)
            box.setAlignment(Qt.AlignRight)
            box.setMinimumWidth(118)
            box.valueChanged.connect(lambda: self._refresh(refit=False))
        add_row("Kopieren", self.copies_x, self.copies_y)

        gap = float(per_file.get("copy_gap", 10))
        self.gap_x = self._mm(0, 5000, float(per_file.get("gap_x", gap)))
        self.gap_y = self._mm(0, 5000, float(per_file.get("gap_y", gap)))
        self.gap_x.valueChanged.connect(lambda: self._refresh(refit=False))
        self.gap_y.valueChanged.connect(lambda: self._refresh(refit=False))
        add_row("Kopierabstand", self.gap_x, self.gap_y)
        add_rule()

        legacy = float(per_file.get("frame_mm", 0))
        self.frame_on = QCheckBox("Rahmen")
        self.frame_on.setChecked(bool(per_file.get("frame_on", legacy > 0)))
        self.frame_on.setToolTip("Rechteck um das Motiv mitschneiden. Das Motiv rückt um den Abstand vom Ursprung weg.")
        self.frame_x = self._mm(0, 500, float(per_file.get("frame_x", legacy or 10)))
        self.frame_y = self._mm(0, 500, float(per_file.get("frame_y", legacy or 10)))
        self.frame_on.toggled.connect(self._on_frame_toggled)
        self.frame_x.valueChanged.connect(lambda: self._refresh(refit=False))
        self.frame_y.valueChanged.connect(lambda: self._refresh(refit=False))
        add_row(self.frame_on, self.frame_x, self.frame_y)
        add_rule()

        totals = QHBoxLayout()
        self.total_w = QLabel()
        self.total_h = QLabel()
        for lab in (self.total_w, self.total_h):
            lab.setObjectName("Total")
            lab.setAlignment(Qt.AlignCenter)
            totals.addWidget(lab, 1)
        grid.addLayout(totals, self._grid_row, 0, 1, 6)
        self._on_frame_toggled(self.frame_on.isChecked(), refresh=False)
        return table

    def _link_label(self) -> QLabel:
        lab = QLabel("—")
        lab.setObjectName("Link")
        lab.setAlignment(Qt.AlignCenter)
        lab.setFixedWidth(16)
        lab.setToolTip("Seitenverhältnis gekoppelt (Verzerren aus)")
        return lab

    def _saved_copies(self, per_file: dict) -> tuple[int, int]:
        if "copies_x" in per_file or "copies_y" in per_file:
            return int(per_file.get("copies_x", 1)), int(per_file.get("copies_y", 1))
        count = int(per_file.get("copies", 1))
        return (count, 1) if per_file.get("copy_axis") == "x" else (1, count)

    def _build_layout_tabs(self, per_file: dict) -> QTabWidget:
        tabs = QTabWidget()

        layout_page = QWidget()
        lay = QVBoxLayout(layout_page)
        lay.setContentsMargins(8, 8, 8, 8)
        icons = QHBoxLayout()
        icons.setSpacing(2)
        icons.addWidget(self._round_button("rotate", "Drehen", "Um 90 Grad drehen", self._rotate_90, 40))
        self.btn_move = self._round_button("move", "Bewegen", "Motiv auf der Folie platzieren", self._open_move, 40)
        icons.addWidget(self.btn_move)
        icons.addWidget(self._round_button(
            "fit", "Anpassen", "Motiv proportional auf die Folie skalieren", self._fit_to_sheet, 40))
        icons.addWidget(self._round_button(
            "original", "Original Layout", "Drehung, Größe, Spiegeln und Lage zurücksetzen", self._reset_original, 40))
        lay.addLayout(icons)

        self._rotate_index = int(per_file.get("rotate_index", 0)) % 4
        opts = QGridLayout()
        opts.setHorizontalSpacing(14)
        self.mirror = QCheckBox("Spiegeln")
        self.mirror.setChecked(bool(per_file.get("mirror", False)))
        self.mirror.toggled.connect(lambda _on: self._on_rotate())
        self.distort = QCheckBox("Verzerren")
        self.distort.setToolTip("Breite und Höhe unabhängig ändern")
        self.distort.setChecked(bool(per_file.get("distort", False)))
        self.distort.toggled.connect(self._on_distort)
        self.fixed_origin = QCheckBox("Nullpunkt fest")
        self.fixed_origin.setToolTip("Motiv bleibt am Plotter-Ursprung, Bewegen und Offset sind aus")
        self.fixed_origin.setChecked(bool(per_file.get("fixed_origin", False)))
        self.fixed_origin.toggled.connect(self._apply_fixed_origin)
        opts.addWidget(self.mirror, 0, 0)
        opts.addWidget(self.distort, 1, 0)
        opts.addWidget(self.fixed_origin, 2, 0)

        mark_mid = QCheckBox("Justiermarke Mitte")
        mark_corner = QCheckBox("Justiermarke Ecke")
        mark_mm = self._mm(0, 100, 10)
        for w in (mark_mid, mark_corner, mark_mm):
            w.setEnabled(False)
            w.setToolTip("Justiermarken folgen in einer späteren Version")
        opts.addWidget(mark_mid, 0, 1)
        opts.addWidget(mark_mm, 0, 2)
        opts.addWidget(mark_corner, 1, 1)
        unit_row = QHBoxLayout()
        unit_row.addWidget(QLabel("Einheit:"))
        unit = ComboBox()
        unit.addItem("mm")
        unit_row.addWidget(unit, 1)
        opts.addLayout(unit_row, 2, 1, 1, 2)
        lay.addLayout(opts)
        tabs.addTab(layout_page, "Layout")

        tabs.addTab(self._placeholder(
            "Kacheln: große Motive in Bahnen mit Überlappung aufteilen. "
            "Kommt in einer späteren Version."), "Kacheln Abstand")
        tabs.addTab(self._placeholder(
            "Passermarken (Konturschnitt nach Druck) kommen in einer späteren Version."), "Passermarken")
        return tabs

    def _placeholder(self, text: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setStyleSheet("color: #777777;")
        lay.addWidget(lab)
        lay.addStretch(1)
        return page

    def _build_color_tabs(self, per_file: dict) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setMinimumHeight(150)
        self.color_list = QListWidget()
        disabled = {c.lower() for c in per_file.get("disabled_colors", [])}
        seen: list[str] = []
        for pl in self.source:
            col = (pl.color or "#000000").lower()
            if col not in seen:
                seen.append(col)
        for col in seen:
            item = QListWidgetItem(_swatch(col), _color_label(col))
            item.setData(Qt.UserRole, col)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if col in disabled else Qt.Checked)
            self.color_list.addItem(item)
        self.color_list.itemChanged.connect(lambda _item: self._refresh(refit=False))
        tabs.addTab(self.color_list, "Farbe")
        tabs.addTab(self._placeholder(
            "Ebenen kommen, sobald VectorCraft sie mit der Auswahl liefert. "
            "Bis dahin über die Farbe wählen."), "Ebene")
        return tabs

    # -- Ereignisse --------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.preview.fit_sheet)

    def _on_tab(self, index: int) -> None:
        self._tab = index
        self.tab_preview.setChecked(index == 0)
        self.tab_lines.setChecked(index == 1)
        self.preview.set_cut_lines(index == 1)
        self._refresh(refit=False)

    def _on_frame_toggled(self, on: bool, refresh: bool = True) -> None:
        self.frame_x.setEnabled(on)
        self.frame_y.setEnabled(on)
        if refresh:
            self._refresh(refit=False)

    def _on_distort(self, on: bool) -> None:
        self.link_size.setText("" if on else "—")
        self.link_scale.setText("" if on else "—")
        if not on:
            self._on_width(self.size_w.value())

    def _apply_fixed_origin(self, *_args) -> None:
        free = not self.fixed_origin.isChecked()
        for w in (self.offset_x, self.offset_y, self.btn_move):
            w.setEnabled(free)
        self._refresh(refit=False)

    def _rotate_degrees(self) -> float:
        return 90.0 * self._rotate_index

    def _corner(self) -> str:
        lang = self.controller.profile["plotter"].get("language", "mgl2")
        return "bottom_right" if lang == "mgl2" else "bottom_left"

    def _oriented(self) -> list[g.Polyline]:
        work = self._enabled_source()
        deg = self._rotate_degrees()
        if deg:
            work = g.rotate(work, deg)
        if self.mirror.isChecked():
            work = g.mirror_x(work)
        return work

    def _enabled_source(self) -> list[g.Polyline]:
        if not hasattr(self, "color_list"):
            return self.source
        off = set(self._disabled_colors())
        picked = [pl for pl in self.source if (pl.color or "#000000").lower() not in off]
        return picked or self.source

    def _disabled_colors(self) -> list[str]:
        out = []
        for i in range(self.color_list.count()):
            item = self.color_list.item(i)
            if item.checkState() != Qt.Checked:
                out.append(item.data(Qt.UserRole))
        return out

    def _natural_size(self) -> tuple[float, float]:
        box = g.bounds_of(self._oriented())
        return (max(box[2] - box[0], 0.1), max(box[3] - box[1], 0.1))

    def _sync_size_from_source(self) -> None:
        self._nat_w, self._nat_h = self._natural_size()
        if self._user_scaled:
            self._sync_scale_from_size()
            return
        self._block = True
        self.size_w.setValue(self._nat_w)
        self.size_h.setValue(self._nat_h)
        self.scale_x.setValue(100.0)
        self.scale_y.setValue(100.0)
        self._block = False

    def _sync_scale_from_size(self) -> None:
        self._block = True
        self.scale_x.setValue(self.size_w.value() / self._nat_w * 100.0)
        self.scale_y.setValue(self.size_h.value() / self._nat_h * 100.0)
        self._block = False

    def _linked(self) -> bool:
        return not self.distort.isChecked()

    def _on_width(self, value: float) -> None:
        if self._block:
            return
        self._user_scaled = True
        self._block = True
        if self._linked() and self._nat_w > 1e-6:
            self.size_h.setValue(value * self._nat_h / self._nat_w)
        self._block = False
        self._sync_scale_from_size()
        self._refresh(refit=False)

    def _on_height(self, value: float) -> None:
        if self._block:
            return
        self._user_scaled = True
        self._block = True
        if self._linked() and self._nat_h > 1e-6:
            self.size_w.setValue(value * self._nat_w / self._nat_h)
        self._block = False
        self._sync_scale_from_size()
        self._refresh(refit=False)

    def _on_scale_x(self, pct: float) -> None:
        if self._block:
            return
        self._block = True
        if self._linked():
            self.scale_y.setValue(pct)
        self._block = False
        self._set_size_from_scale()

    def _on_scale_y(self, pct: float) -> None:
        if self._block:
            return
        self._block = True
        if self._linked():
            self.scale_x.setValue(pct)
        self._block = False
        self._set_size_from_scale()

    def _set_size_from_scale(self) -> None:
        self._user_scaled = True
        self._block = True
        self.size_w.setValue(self._nat_w * self.scale_x.value() / 100.0)
        self.size_h.setValue(self._nat_h * self.scale_y.value() / 100.0)
        self._block = False
        self._refresh(refit=False)

    def _on_rotate(self) -> None:
        if self._block:
            return
        self._user_scaled = False
        self._sync_size_from_source()
        self._refresh(refit=False)

    def _rotate_90(self) -> None:
        self._rotate_index = (self._rotate_index + 1) % 4
        self._on_rotate()

    def _fit_to_sheet(self) -> None:
        frame_x, frame_y = self._frame_margins()
        avail_w = self.sheet_width.value() - 2 * frame_x
        avail_h = self.sheet_height.value() - 2 * frame_y
        if avail_w <= 0 or avail_h <= 0:
            return
        factor = min(avail_w / self._nat_w, avail_h / self._nat_h)
        self._user_scaled = True
        self._block = True
        self.size_w.setValue(self._nat_w * factor)
        self.size_h.setValue(self._nat_h * factor)
        self.offset_x.setValue(0)
        self.offset_y.setValue(0)
        self._block = False
        self._anchor = (0.0, 0.0)
        self._sync_scale_from_size()
        self._refresh(refit=True)

    def _reset_original(self) -> None:
        self._block = True
        self._rotate_index = 0
        self.mirror.setChecked(False)
        self.distort.setChecked(False)
        self.offset_x.setValue(0)
        self.offset_y.setValue(0)
        self._block = False
        self._anchor = (0.0, 0.0)
        self._user_scaled = False
        self._on_distort(False)
        self._sync_size_from_source()
        self._refresh(refit=True)

    def _initialize(self) -> None:
        self._block = True
        self.copies_x.setValue(1)
        self.copies_y.setValue(1)
        self.gap_x.setValue(10)
        self.gap_y.setValue(10)
        self.frame_on.setChecked(False)
        self.fixed_origin.setChecked(False)
        for i in range(self.color_list.count()):
            self.color_list.item(i).setCheckState(Qt.Checked)
        self._block = False
        self._on_frame_toggled(False, refresh=False)
        self._apply_fixed_origin()
        self._read_sheet_size()
        self._reset_original()

    def _read_sheet_size(self) -> None:
        plotter = self.controller.profile["plotter"]
        self._block = True
        self.sheet_width.setValue(float(plotter.get("sheet_width_mm", 610)))
        self.sheet_height.setValue(float(plotter.get("sheet_height_mm", 1000)))
        self._block = False
        self._refresh(refit=True)

    def _open_move(self) -> None:
        dlg = MoveDialog(self, self._corner(), self._anchor)
        if dlg.exec() == QDialog.Accepted and dlg.anchor is not None:
            self._anchor = dlg.anchor
            self._block = True
            self.offset_x.setValue(0)
            self.offset_y.setValue(0)
            self._block = False
            self._refresh(refit=False)

    # -- Geometrie ---------------------------------------------------------

    def _frame_margins(self) -> tuple[float, float]:
        if not self.frame_on.isChecked():
            return (0.0, 0.0)
        return (self.frame_x.value(), self.frame_y.value())

    def _transformed(self) -> list[g.Polyline]:
        work = self._oriented()
        nat_w, nat_h = self._natural_size()
        sx = self.size_w.value() / nat_w if nat_w else 1.0
        sy = self.size_h.value() / nat_h if nat_h else 1.0
        if abs(sx - 1.0) > 1e-6 or abs(sy - 1.0) > 1e-6:
            work = g.scale(work, sx, sy)
        work = g.align_to_origin(work, corner=self._corner())
        work = _with_frame(work, *self._frame_margins())
        work = _tile_copies(
            work,
            self.copies_x.value(),
            self.copies_y.value(),
            self.gap_x.value(),
            self.gap_y.value(),
        )
        if not self.fixed_origin.isChecked():
            minx, miny, maxx, maxy = g.bounds_of(work)
            ax, ay = self._anchor
            dx = ax * max(self.sheet_width.value() - (maxx - minx), 0.0) + self.offset_x.value()
            dy = ay * max(self.sheet_height.value() - (maxy - miny), 0.0) + self.offset_y.value()
            if dx or dy:
                work = g.translate(work, dx, dy)
        return work

    def _refresh(self, refit: bool = False) -> None:
        if self._block:
            return
        work = self._transformed()
        self.preview.origin_corner = self._corner()
        self.preview.set_cut_lines(self._tab == 1)
        self.preview.set_data(
            work,
            self.sheet_width.value(),
            refit=False,
            sheet_height_mm=self.sheet_height.value(),
        )
        minx, miny, maxx, maxy = g.bounds_of(work)
        w, h = maxx - minx, maxy - miny
        self.total_w.setText(f"{H_ARROW} {w:.1f} mm")
        self.total_h.setText(f"{V_ARROW} {h:.1f} mm")
        too_wide = maxx > self.sheet_width.value() + 1e-6
        self.total_w.setStyleSheet("color: #c62828;" if too_wide else "")
        self.total_w.setToolTip("Breiter als die Folie" if too_wide else "")
        if refit:
            self.preview.fit_sheet()

    # -- Speichern / weiter ------------------------------------------------

    def _persist(self) -> None:
        self.controller.store_per_file(
            self.document_path,
            {
                "rotate_index": self._rotate_index,
                "mirror": self.mirror.isChecked(),
                "distort": self.distort.isChecked(),
                "fixed_origin": self.fixed_origin.isChecked(),
                "copies_x": self.copies_x.value(),
                "copies_y": self.copies_y.value(),
                "gap_x": self.gap_x.value(),
                "gap_y": self.gap_y.value(),
                "offset_x": self.offset_x.value(),
                "offset_y": self.offset_y.value(),
                "anchor": list(self._anchor),
                "frame_on": self.frame_on.isChecked(),
                "frame_x": self.frame_x.value(),
                "frame_y": self.frame_y.value(),
                "disabled_colors": self._disabled_colors(),
            },
        )

    def _open_plot_out(self) -> None:
        from .plot_out_dialog import PlotOutDialog

        self._persist()
        try:
            dlg = PlotOutDialog(
                self.controller,
                source=self._transformed(),
                sheet_width_mm=self.sheet_width.value(),
                copies=1,
                document_path=self.document_path,
                origin=self._corner(),
                already_placed=True,
                parent=self,
                sheet_height_mm=self.sheet_height.value(),
            )
            if dlg.exec() == QDialog.Accepted:
                self.accept()
        except Exception as exc:
            critical(self, "Ausplotten", f"Das Ausplotten-Fenster konnte nicht geoeffnet werden:\n{exc}")


class MoveDialog(QDialog):
    """FineCut "Bewegen": Motiv an eine von neun Stellen der Folie legen."""

    ARROWS = ["↖", "↑", "↗", "←", "•", "→", "↙", "↓", "↘"]

    def __init__(self, parent: QWidget, corner: str, current: tuple[float, float]) -> None:
        super().__init__(parent)
        self.anchor: tuple[float, float] | None = None
        self._corner = corner
        self.setWindowTitle("Bewegen")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(FINECUT_STYLE)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Position auf der Folie"))
        grid = QGridLayout()
        grid.setSpacing(4)
        for i, arrow in enumerate(self.ARROWS):
            row, col = divmod(i, 3)
            btn = QPushButton(arrow)
            btn.setFixedSize(46, 40)
            btn.setStyleSheet("font-size: 18px;")
            anchor = self._anchor_for(col, row)
            if _same(anchor, current):
                btn.setStyleSheet("font-size: 18px; background: #d7eadc; border: 1px solid #2d7d46;")
            btn.clicked.connect(lambda _c=False, a=anchor: self._pick(a))
            grid.addWidget(btn, row, col)
        lay.addLayout(grid)
        close = QPushButton("Abbrechen")
        close.clicked.connect(self.reject)
        lay.addWidget(close)

    def _anchor_for(self, col: int, row: int) -> tuple[float, float]:
        ax = (2 - col) / 2.0 if self._corner == "bottom_right" else col / 2.0
        return (ax, (2 - row) / 2.0)

    def _pick(self, anchor: tuple[float, float]) -> None:
        self.anchor = anchor
        self.accept()


def _same(a: tuple[float, float], b) -> bool:
    try:
        return abs(a[0] - float(b[0])) < 1e-6 and abs(a[1] - float(b[1])) < 1e-6
    except (TypeError, ValueError, IndexError):
        return False


def _swatch(color: str) -> QIcon:
    pm = QPixmap(14, 14)
    pm.fill(QColor(color))
    return QIcon(pm)


def _color_label(color: str) -> str:
    c = QColor(color)
    return f"R={c.red()} G={c.green()} B={c.blue()}"


def _with_frame(polylines: list[g.Polyline], margin_x: float, margin_y: float | None = None) -> list[g.Polyline]:
    """Rechteck um das Motiv. Die Ecke am Ursprung bleibt, das Motiv rückt um den Abstand weg."""
    if margin_y is None:
        margin_y = margin_x
    if (margin_x <= 0 and margin_y <= 0) or not polylines:
        return polylines
    minx, miny, maxx, maxy = g.bounds_of(polylines)
    moved = g.translate(polylines, margin_x, margin_y)
    x1, y1 = maxx + 2 * margin_x, maxy + 2 * margin_y
    frame = g.Polyline(
        [(minx, miny), (x1, miny), (x1, y1), (minx, y1), (minx, miny)],
        closed=True,
        color="#111111",
        kind="frame",
    )
    return [*moved, frame]


def _tile_copies(
    polylines: list[g.Polyline],
    copies_x: int,
    copies_y: int = 1,
    gap_x: float = 0.0,
    gap_y: float = 0.0,
) -> list[g.Polyline]:
    """Kopien als Raster: ``copies_x`` entlang der Folienbreite, ``copies_y`` im Vorschub."""
    if (copies_x <= 1 and copies_y <= 1) or not polylines:
        return polylines
    minx, miny, maxx, maxy = g.bounds_of(polylines)
    step_x = (maxx - minx) + max(gap_x, 0.0)
    step_y = (maxy - miny) + max(gap_y, 0.0)
    out: list[g.Polyline] = []
    for iy in range(max(1, copies_y)):
        for ix in range(max(1, copies_x)):
            out.extend(g.translate(polylines, ix * step_x, iy * step_y))
    return out
