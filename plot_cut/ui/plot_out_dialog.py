"""[Ausplotten]-Fenster im FineCut-Look: Plot-Einstellung, Bedingung je Farbe,
Optionen und rechts die Knoepfe Schneiden / Vorschau / Datei / Preset."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import geometry as g
from .. import i18n
from .. import mgl
from ..transport import TransportError, build_transport
from .popup import critical, information, question
from .preview import PreviewWidget, view_buttons
from .style import FINECUT_STYLE, ComboBox

if TYPE_CHECKING:
    from ..app import AppController

_OUT_STYLE = """
QGroupBox { font-weight: 500; }
QLabel:disabled, QCheckBox:disabled, QRadioButton:disabled { color: #9a9a9a; }
QPushButton#Side { min-width: 170px; }
"""

SAME_AS_ABOVE = "__same__"
DO_NOT_CUT = "__skip__"


class PlotOutDialog(QDialog):
    def __init__(
        self,
        controller: AppController,
        source: list[g.Polyline],
        sheet_width_mm: float,
        copies: int,
        document_path: str | None,
        origin: str = "bottom_right",
        already_placed: bool = False,
        parent: object | None = None,
        sheet_height_mm: float = 1000.0,
    ) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.controller = controller
        self.source = source
        self.sheet_width_mm = sheet_width_mm
        self.sheet_height_mm = sheet_height_mm
        self.copies = copies
        self.document_path = document_path
        self.origin = origin
        # Bereits gesetzter Offset darf in prepare_job nicht wieder auf 0 fallen.
        self.job_origin = "keep" if already_placed else origin

        self.setWindowTitle(i18n.trf("Ausplotten — {name}", name=controller.profile_name))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(FINECUT_STYLE + _OUT_STYLE)
        self.resize(920, 760)

        d = controller.profile["defaults"]
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(12)
        root.addLayout(left, 1)
        left.addWidget(self._build_plot_setting(d))
        left.addWidget(self._build_options(d))
        self.info = QLabel("")
        self.info.setStyleSheet("color: #444444;")
        left.addWidget(self.info)
        left.addStretch(1)

        right = QVBoxLayout()
        right.setSpacing(10)
        root.addLayout(right)
        buttons = [
            ("Schneiden", self._on_plot, True),
            ("Abbrechen", self.reject, False),
            ("Vorschau...", self._open_preview, False),
            ("Speichern als Datei...", self._on_save_file, False),
            ("Save Preset Setting", self._save_preset, False),
        ]
        for text, handler, primary in buttons:
            btn = QPushButton(i18n.tr(text))
            btn.setObjectName("Primary" if primary else "Side")
            btn.setMinimumWidth(190)
            btn.clicked.connect(handler)
            if primary:
                btn.setDefault(True)
            right.addWidget(btn)
        right.addStretch(1)

        self._update_enabled()
        self._on_source_changed()
        self._update_info()

    # -- Aufbau ------------------------------------------------------------

    def _build_plot_setting(self, d: dict) -> QGroupBox:
        box = QGroupBox(i18n.tr("Plot-Einstellung"))
        grid = QGridLayout(box)
        grid.setContentsMargins(14, 16, 14, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnMinimumWidth(1, 150)

        self.src_plotter = QRadioButton(i18n.tr("Plotter-Einstellung"))
        self.src_preset = QRadioButton(i18n.tr("Auswahl-Einstellung"))
        self.src_custom = QRadioButton(i18n.tr("Benutzerdefiniert"))
        self.src_group = QButtonGroup(self)
        for i, rb in enumerate((self.src_plotter, self.src_preset, self.src_custom)):
            self.src_group.addButton(rb, i)

        source = d.get("condition_source")
        if source not in ("plotter", "preset", "custom"):
            source = "custom" if d.get("send_conditions", True) else "plotter"
        {"plotter": self.src_plotter, "preset": self.src_preset, "custom": self.src_custom}[source].setChecked(True)

        grid.addWidget(self.src_plotter, 0, 0, 1, 2)

        grid.addWidget(self.src_preset, 1, 0)
        self.preset_combo = ComboBox()
        self._reload_presets(d.get("preset", ""))
        grid.addWidget(self.preset_combo, 1, 1, 1, 2)
        self.preset_edit = QPushButton(i18n.tr("Bearbeiten..."))
        self.preset_edit.setToolTip(i18n.tr("Presets im Setup verwalten"))
        self.preset_edit.clicked.connect(self._edit_presets)
        grid.addWidget(self.preset_edit, 1, 3)

        grid.addWidget(self.src_custom, 2, 0)
        self.tool_label = i18n.lab("Werkzeug")
        grid.addWidget(self.tool_label, 3, 1)
        self.tool = ComboBox()
        for label, value in mgl.TOOLS:
            self.tool.addItem(label, value)
        self.tool.setCurrentIndex(max(0, self.tool.findData(int(d.get("tool", 1)))))
        grid.addWidget(self.tool, 3, 2)

        lang = str(self.controller.profile["plotter"].get("language", "mgl2"))
        self.use_speed = QCheckBox(i18n.tr("Geschwindigkeit"))
        self.speed = QSpinBox()
        lo, hi = mgl.speed_range(lang)
        self.speed.setRange(lo, hi)
        self.speed.setValue(int(d.get("speed", 30)))
        self.use_pressure = QCheckBox(i18n.tr("Andruck"))
        self.pressure = QSpinBox()
        lo, hi = mgl.pressure_range(lang)
        self.pressure.setRange(lo, hi)
        self.pressure.setValue(int(d.get("pressure", 100)))
        self.use_offset = QCheckBox(i18n.tr("Offset"))
        self.offset = QDoubleSpinBox()
        self.offset.setRange(0.0, 2.0)
        self.offset.setSingleStep(0.05)
        self.offset.setValue(float(d.get("offset", 0.3)))
        self._custom_rows = []
        for row, (check, spin, unit, key) in enumerate(
            (
                (self.use_speed, self.speed, "cm/s", "use_speed"),
                (self.use_pressure, self.pressure, "g", "use_pressure"),
                (self.use_offset, self.offset, "mm", "use_offset"),
            ),
            start=4,
        ):
            check.setChecked(bool(d.get(key, True)))
            check.toggled.connect(self._update_enabled)
            spin.setAlignment(Qt.AlignRight)
            unit_label = QLabel(unit)
            grid.addWidget(check, row, 1)
            grid.addWidget(spin, row, 2)
            grid.addWidget(unit_label, row, 3)
            self._custom_rows.append((check, spin, unit_label))

        per_color = QGroupBox(i18n.tr("Schneidbedingung je Farbe"))
        pc = QGridLayout(per_color)
        pc.setContentsMargins(12, 14, 12, 10)
        pc.addWidget(i18n.lab("Farbe"), 0, 0)
        self.color_combo = ComboBox()
        self.color_combo.currentIndexChanged.connect(self._show_color_condition)
        pc.addWidget(self.color_combo, 0, 1)
        pc.addWidget(i18n.lab("Bedingung"), 1, 0)
        self.color_condition = ComboBox()
        self.color_condition.activated.connect(self._store_color_condition)
        pc.addWidget(self.color_condition, 1, 1)
        pc.setColumnStretch(1, 1)
        grid.addWidget(per_color, 7, 0, 1, 4)

        self.src_group.idToggled.connect(lambda _id, _on: self._update_enabled())
        self._update_enabled()
        return box

    def _build_options(self, d: dict) -> QGroupBox:
        box = QGroupBox(i18n.tr("Optionen"))
        grid = QGridLayout(box)
        grid.setContentsMargins(14, 16, 14, 14)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)

        self.sort = QCheckBox(i18n.tr("Sortieren"))
        self.sort.setChecked(bool(d.get("sort", True)))
        self.sort_all = QRadioButton(i18n.tr("Alle"))
        self.sort_color = QRadioButton(i18n.tr("Jede Farbe"))
        (self.sort_color if d.get("sort_mode") == "color" else self.sort_all).setChecked(True)
        self.inner_first = QCheckBox(i18n.tr("Innen vor Außen"))
        self.inner_first.setChecked(bool(d.get("inner_first", True)))
        self.sort.toggled.connect(self._update_enabled)
        for w in (self.sort, self.sort_all, self.sort_color, self.inner_first):
            w.toggled.connect(self._update_info)
        grid.addWidget(self.sort, 0, 0)
        grid.addWidget(_indent(self.sort_all), 1, 0)
        grid.addWidget(_indent(self.sort_color), 2, 0)
        grid.addWidget(_indent(self.inner_first), 3, 0)

        self.park = QCheckBox(i18n.tr("Kopf in Parkposition"))
        self.park.setToolTip(i18n.tr(
            "Nach dem Schnitt fährt der Kopf hinter das Motiv, damit die Folie abgeschnitten werden kann."
        ))
        self.park.setChecked(bool(d.get("park", True)))
        self.park_gap = QDoubleSpinBox()
        self.park_gap.setRange(0.0, 1000.0)
        self.park_gap.setSuffix(" mm")
        self.park_gap.setValue(float(d.get("park_mm", 20.0)))
        self.park_gap.setToolTip(i18n.tr("Abstand hinter dem Motiv"))
        self.park.toggled.connect(self._update_enabled)
        grid.addWidget(self.park, 4, 0)
        park_row = QHBoxLayout()
        park_row.addWidget(i18n.lab("Abstand"))
        park_row.addWidget(self.park_gap)
        park_row.addStretch(1)
        grid.addLayout(_indent_layout(park_row), 5, 0)

        overcut_row = QHBoxLayout()
        overcut_row.addWidget(i18n.lab("Overcut"))
        self.overcut = QDoubleSpinBox()
        self.overcut.setRange(0.0, 10.0)
        self.overcut.setSingleStep(0.1)
        self.overcut.setSuffix(" mm")
        self.overcut.setValue(float(d.get("overcut_mm", 0.0)))
        self.overcut.valueChanged.connect(self._update_info)
        overcut_row.addWidget(self.overcut)
        overcut_row.addStretch(1)
        grid.addLayout(overcut_row, 0, 1)

        self.extra_passes = QSpinBox()
        self.extra_passes.setRange(0, 9)
        self.extra_passes.setValue(int(d.get("extra_passes", 0)))
        self.extra_passes.setToolTip(i18n.tr("Zusätzliche Schnitte über denselben Pfad"))
        extra_row = QHBoxLayout()
        extra_row.addWidget(i18n.lab("Mehrfachschnitt"))
        extra_row.addWidget(self.extra_passes)
        extra_row.addStretch(1)
        grid.addLayout(extra_row, 1, 1)

        self.pause_color = QCheckBox(i18n.tr("Nach jeder Farbe anhalten"))
        self.pause_color.setChecked(bool(d.get("pause_per_color", False)))
        grid.addWidget(self.pause_color, 2, 1)

        self.end_origin = QRadioButton(i18n.tr("Zum Ursprung"))
        self.end_feed = QRadioButton(i18n.tr("Folie vorschieben"))
        self.end_stay = QRadioButton(i18n.tr("Stehen bleiben"))
        self.end_group = QButtonGroup(self)
        for i, rb in enumerate((self.end_origin, self.end_feed, self.end_stay)):
            self.end_group.addButton(rb, i)
        action = d.get("end_action", "stay")
        {"origin": self.end_origin, "feed": self.end_feed}.get(action, self.end_stay).setChecked(True)
        grid.addWidget(i18n.lab("Nach dem Schnitt"), 3, 1)
        grid.addWidget(self.end_origin, 4, 1)
        self.feed_mm = QDoubleSpinBox()
        self.feed_mm.setRange(0.0, 5000.0)
        self.feed_mm.setSuffix(" mm")
        self.feed_mm.setValue(float(d.get("feed_mm", 20.0)))
        feed_row = QHBoxLayout()
        feed_row.addWidget(self.end_feed)
        feed_row.addWidget(self.feed_mm)
        feed_row.addStretch(1)
        grid.addLayout(feed_row, 5, 1)
        grid.addWidget(self.end_stay, 6, 1)
        self.end_feed.toggled.connect(lambda on: self.feed_mm.setEnabled(on))
        self.feed_mm.setEnabled(self.end_feed.isChecked())
        grid.setColumnStretch(1, 1)
        return box

    # -- Zustand -----------------------------------------------------------

    def _condition_source(self) -> str:
        if self.src_plotter.isChecked():
            return "plotter"
        if self.src_preset.isChecked():
            return "preset"
        return "custom"

    def _update_enabled(self, *_args) -> None:
        preset = self.src_preset.isChecked()
        custom = self.src_custom.isChecked()
        self.preset_combo.setEnabled(preset)
        self.preset_edit.setEnabled(preset)
        self.tool_label.setEnabled(custom)
        self.tool.setEnabled(custom)
        for check, spin, unit in self._custom_rows:
            check.setEnabled(custom)
            spin.setEnabled(custom and check.isChecked())
            unit.setEnabled(custom and check.isChecked())
        if hasattr(self, "sort_all"):
            for w in (self.sort_all, self.sort_color, self.inner_first):
                w.setEnabled(self.sort.isChecked())
            self.park_gap.setEnabled(self.park.isChecked())

    def _presets(self) -> dict:
        return self.controller.settings.get("favorites", {})

    def _reload_presets(self, select: str = "") -> None:
        self.preset_combo.clear()
        names = sorted(self._presets().keys())
        if not names:
            self.preset_combo.addItem(i18n.tr("(keine Presets gespeichert)"), "")
        for name in names:
            self.preset_combo.addItem(name, name)
        if select:
            idx = self.preset_combo.findData(select)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)

    def _edit_presets(self) -> None:
        current = self.preset_combo.currentData() or ""
        self.controller.on_setup()
        self._reload_presets(current)
        self._reload_color_conditions()

    def _on_source_changed(self) -> None:
        colors: list[str] = []
        for pl in self.source:
            if pl.kind == "frame":
                continue
            col = (pl.color or "#000000").lower()
            if col not in colors:
                colors.append(col)
        self.color_combo.blockSignals(True)
        self.color_combo.clear()
        for col in colors:
            self.color_combo.addItem(col.upper(), col)
        self.color_combo.blockSignals(False)
        self._reload_color_conditions()

    def _reload_color_conditions(self) -> None:
        self.color_condition.clear()
        self.color_condition.addItem(i18n.tr("Wie Plot-Einstellung"), SAME_AS_ABOVE)
        for name in sorted(self._presets().keys()):
            self.color_condition.addItem(i18n.trf("Preset: {name}", name=name), name)
        self.color_condition.addItem(i18n.tr("Nicht schneiden"), DO_NOT_CUT)
        self._show_color_condition()

    def _show_color_condition(self, *_args) -> None:
        color = self.color_combo.currentData()
        raw = self.controller.profile.get("conditions_by_color", {}).get(color or "", None)
        key = SAME_AS_ABOVE
        if isinstance(raw, dict):
            key = DO_NOT_CUT if not raw.get("enabled", True) else raw.get("preset", SAME_AS_ABOVE)
        idx = self.color_condition.findData(key)
        self.color_condition.setCurrentIndex(max(0, idx))

    def _store_color_condition(self, *_args) -> None:
        color = self.color_combo.currentData()
        if not color:
            return
        table = self.controller.profile.setdefault("conditions_by_color", {})
        key = self.color_condition.currentData()
        if key == SAME_AS_ABOVE:
            table.pop(color, None)
        elif key == DO_NOT_CUT:
            table[color] = {"enabled": False}
        else:
            fav = self._presets().get(key, {})
            table[color] = {
                "preset": key,
                "tool": int(fav.get("tool", 1)),
                "speed": int(fav.get("speed", 30)),
                "pressure": int(fav.get("pressure", 100)),
                "offset": float(fav.get("offset", 0.3)),
                "enabled": True,
            }
        self.controller.save()
        self._update_info()

    def _main_condition(self) -> mgl.CutCondition:
        source = self._condition_source()
        if source == "preset":
            fav = self._presets().get(self.preset_combo.currentData() or "", {})
            return mgl.CutCondition(
                tool=int(fav.get("tool", 1)),
                speed=int(fav.get("speed", 30)),
                pressure=int(fav.get("pressure", 100)),
                offset=float(fav.get("offset", 0.3)),
            )
        return mgl.CutCondition(
            tool=int(self.tool.currentData() or 1),
            speed=self.speed.value() if self.use_speed.isChecked() else None,
            pressure=self.pressure.value() if self.use_pressure.isChecked() else None,
            offset=self.offset.value() if self.use_offset.isChecked() else None,
        )

    # -- Auftrag -----------------------------------------------------------

    def _build_job(self) -> g.CutJob:
        return g.prepare_job(
            self.source,
            rotate_deg=0.0,
            mirror=False,
            overcut_mm=self.overcut.value(),
            sort=self.sort.isChecked(),
            inner_first=self.inner_first.isChecked(),
            origin=self.job_origin,
        )

    def _update_info(self, *_args) -> None:
        if not hasattr(self, "info"):
            return
        job = self._build_job()
        self.info.setText(i18n.trf(
            "Pfade: {n}    Schnittlänge: {cm} cm",
            n=len(job.polylines),
            cm=f"{job.total_cut_mm / 10.0:.1f}",
        ))

    def _end_action(self) -> str:
        if self.end_origin.isChecked():
            return "origin"
        if self.end_feed.isChecked():
            return "feed"
        return "stay"

    def _plot_options(self, job: g.CutJob) -> mgl.PlotOptions:
        plotter = self.controller.profile["plotter"]
        park = None
        if self.park.isChecked() and job.polylines:
            _minx, _miny, _maxx, maxy = g.bounds_of(job.polylines)
            park = (0.0, maxy + self.park_gap.value())
        return mgl.PlotOptions(
            language=str(plotter.get("language", "mgl2")),
            emit_conditions=self._condition_source() != "plotter",
            group_by_color=self.sort_color.isChecked() or not self.sort.isChecked(),
            park_mm=park,
            step_mm=float(plotter.get("step_mm", 0.025)),
            end_action=self._end_action(),
            feed_mm=self.feed_mm.value(),
            extra_passes=self.extra_passes.value(),
        )

    def _generate_bytes(self) -> bytes:
        chunks = self._generate_chunks(split_colors=False)
        return chunks[0] if chunks else b""

    def _generate_chunks(self, split_colors: bool) -> list[bytes]:
        job = self._build_job()
        return mgl.generate_chunk_bytes(
            job,
            conditions_by_color=self.controller.conditions_by_color(),
            default_condition=self._main_condition(),
            options=self._plot_options(job),
            copies=self.copies,
            split_colors=split_colors,
        )

    # -- Knoepfe -----------------------------------------------------------

    def _open_preview(self) -> None:
        dlg = CutPreviewDialog(self, self._build_job(), self.sheet_width_mm, self.sheet_height_mm, self.origin)
        dlg.exec()

    def _save_preset(self) -> None:
        dlg = QInputDialog(self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
        dlg.setWindowTitle(i18n.tr("Save Preset Setting"))
        dlg.setLabelText(i18n.tr("Name für die aktuelle Schneidbedingung:"))
        if dlg.exec() != QDialog.Accepted:
            return
        name = dlg.textValue().strip()
        if not name:
            return
        cond = self._main_condition()
        self.controller.settings.setdefault("favorites", {})[name] = {
            "tool": cond.tool,
            "speed": cond.speed if cond.speed is not None else self.speed.value(),
            "pressure": cond.pressure if cond.pressure is not None else self.pressure.value(),
            "offset": cond.offset if cond.offset is not None else self.offset.value(),
        }
        self.controller.save()
        self._reload_presets(name)
        self._reload_color_conditions()
        information(self, "Preset", i18n.trf('Preset "{name}" gespeichert.', name=name))

    def _on_plot(self) -> None:
        self._persist_defaults()
        split = self.pause_color.isChecked()
        chunks = self._generate_chunks(split_colors=split)
        transport = build_transport(self.controller.profile["transport"])
        sent = 0
        for i, data in enumerate(chunks):
            if i > 0:
                if not question(
                    self,
                    "Nächste Farbe",
                    "Die nächste Farbe ist bereit. Folie wechseln oder Blatt prüfen, dann Ja zum Weiterschneiden.",
                ):
                    break
            try:
                transport.send(data)
            except TransportError as exc:
                critical(self, "Senden fehlgeschlagen", str(exc))
                return
            sent += len(data)
        information(self, "Schneiden", i18n.trf(
            "Gesendet an {where} ({n} Bytes).", where=transport.describe(), n=sent
        ))
        self.accept()

    def _on_save_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, i18n.tr("Plotdatei speichern"), "out.plt", i18n.tr("Plot (*.plt)")
        )
        if not path:
            return
        self._persist_defaults()
        data = self._generate_bytes()
        try:
            with open(path, "wb") as fh:
                fh.write(data)
        except OSError as exc:
            critical(self, "Fehler", str(exc))
            return
        information(self, "Gespeichert", i18n.trf("{n} Bytes nach {path}.", n=len(data), path=path))

    def _persist_defaults(self) -> None:
        source = self._condition_source()
        self.controller.profile["defaults"].update(
            {
                "condition_source": source,
                "preset": self.preset_combo.currentData() or "",
                "tool": int(self.tool.currentData() or 1),
                "speed": self.speed.value(),
                "pressure": self.pressure.value(),
                "offset": self.offset.value(),
                "use_speed": self.use_speed.isChecked(),
                "use_pressure": self.use_pressure.isChecked(),
                "use_offset": self.use_offset.isChecked(),
                "overcut_mm": self.overcut.value(),
                "sort": self.sort.isChecked(),
                "sort_mode": "color" if self.sort_color.isChecked() else "all",
                "inner_first": self.inner_first.isChecked(),
                "park": self.park.isChecked(),
                "park_mm": self.park_gap.value(),
                "send_conditions": source != "plotter",
                "end_action": self._end_action(),
                "feed_mm": self.feed_mm.value(),
                "extra_passes": self.extra_passes.value(),
                "pause_per_color": self.pause_color.isChecked(),
            }
        )
        self.controller.save()


class CutPreviewDialog(QDialog):
    """Vorschau des Schneidauftrags: Richtung, Reihenfolge, Leerfahrten, Simulation."""

    def __init__(
        self,
        parent: QWidget,
        job: g.CutJob,
        sheet_width_mm: float,
        sheet_height_mm: float,
        origin: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("Vorschau"))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(FINECUT_STYLE)
        self.resize(1100, 720)

        root = QHBoxLayout(self)
        self.preview = PreviewWidget(mode="plot_out")
        self.preview.origin_corner = origin
        root.addWidget(self.preview, 1)

        side = QVBoxLayout()
        root.addLayout(side)
        self.arrows = QCheckBox(i18n.tr("Richtungspfeile"))
        self.order = QCheckBox(i18n.tr("Reihenfolge-Nummern"))
        self.order.setChecked(True)
        self.travel = QCheckBox(i18n.tr("Leerfahrten (gelb)"))
        self.travel.setChecked(True)
        for w in (self.arrows, self.order, self.travel):
            w.toggled.connect(self._apply_options)
            side.addWidget(w)
        legend = i18n.lab("schwarz = gegen Uhrzeigersinn\nrot = im Uhrzeigersinn\ngelb = Leerfahrt")
        legend.setStyleSheet("color: #555555;")
        side.addWidget(legend)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self.btn_sim = QPushButton(i18n.tr("Simulation"))
        self.btn_sim.setCheckable(True)
        self.btn_sim.toggled.connect(self._toggle_sim)
        side.addWidget(self.btn_sim)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(100)
        self.slider.valueChanged.connect(lambda v: self.preview.set_sim_progress(v / 100.0))
        side.addWidget(self.slider)
        side.addLayout(view_buttons(self.preview))
        side.addWidget(QLabel(i18n.trf(
            "Schnittlänge: {cm} cm", cm=f"{job.total_cut_mm / 10.0:.1f}"
        )))
        side.addStretch(1)
        close = QPushButton(i18n.tr("Schließen"))
        close.clicked.connect(self.accept)
        side.addWidget(close)

        self.preview.set_data(job.polylines, sheet_width_mm, refit=True, sheet_height_mm=sheet_height_mm)
        self._apply_options()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.preview.fit_sheet)

    def _apply_options(self, *_args) -> None:
        self.preview.set_options(
            arrows=self.arrows.isChecked(),
            order=self.order.isChecked(),
            travel=self.travel.isChecked(),
        )

    def _toggle_sim(self, on: bool) -> None:
        if on:
            self.slider.setValue(0)
            self._timer.start(40)
        else:
            self._timer.stop()
            self.slider.setValue(100)

    def _advance(self) -> None:
        val = min(100, self.slider.value() + 2)
        self.slider.setValue(val)
        if val >= 100:
            self._timer.stop()
            self.btn_sim.setChecked(False)


def _indent(widget: QWidget) -> QWidget:
    host = QWidget()
    lay = QHBoxLayout(host)
    lay.setContentsMargins(24, 0, 0, 0)
    lay.addWidget(widget)
    lay.addStretch(1)
    return host


def _indent_layout(inner: QHBoxLayout) -> QHBoxLayout:
    inner.setContentsMargins(24, 0, 0, 0)
    return inner
