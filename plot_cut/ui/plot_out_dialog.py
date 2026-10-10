"""[Plot Out]-Fenster: Schneidbedingungen, Vorschau mit Farbcodes und
Simulation, Senden an den Plotter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from .. import geometry as g
from .. import mgl
from ..transport import TransportError, build_transport
from .preview import PreviewWidget, view_buttons

if TYPE_CHECKING:
    from ..app import AppController


class PlotOutDialog(QDialog):
    def __init__(
        self,
        controller: AppController,
        source: list[g.Polyline],
        sheet_width_mm: float,
        copies: int,
        document_path: str | None,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.source = source
        self.sheet_width_mm = sheet_width_mm
        self.copies = copies
        self.document_path = document_path

        self.setWindowTitle(f"Plot Out - {controller.profile_name}")
        self.resize(960, 640)
        self._first_refresh = True

        self._sim_timer = QTimer(self)
        self._sim_timer.timeout.connect(self._advance_sim)

        defaults = controller.profile["defaults"]

        root = QHBoxLayout(self)
        self.preview = PreviewWidget(mode="plot_out")
        root.addWidget(self.preview, 3)

        side = QVBoxLayout()
        root.addLayout(side, 1)

        cond = QGroupBox("Schneidbedingung")
        clay = QVBoxLayout(cond)

        clay.addWidget(QLabel("Geschwindigkeit (cm/s)"))
        self.speed = QSpinBox()
        self.speed.setRange(1, 100)
        self.speed.setValue(int(defaults.get("speed", 30)))
        clay.addWidget(self.speed)

        clay.addWidget(QLabel("Druck (g)"))
        self.pressure = QSpinBox()
        self.pressure.setRange(10, 500)
        self.pressure.setValue(int(defaults.get("pressure", 100)))
        clay.addWidget(self.pressure)

        clay.addWidget(QLabel("Klingenoffset (mm)"))
        self.offset = QDoubleSpinBox()
        self.offset.setRange(0.0, 2.0)
        self.offset.setSingleStep(0.05)
        self.offset.setValue(float(defaults.get("offset", 0.3)))
        clay.addWidget(self.offset)

        clay.addWidget(QLabel("Overcut (mm)"))
        self.overcut = QDoubleSpinBox()
        self.overcut.setRange(0.0, 10.0)
        self.overcut.setSingleStep(0.1)
        self.overcut.setValue(float(defaults.get("overcut_mm", 0.0)))
        clay.addWidget(self.overcut)

        self.sort = QCheckBox("Schneidreihenfolge optimieren")
        self.sort.setChecked(bool(defaults.get("sort", True)))
        self.sort.stateChanged.connect(self._refresh)
        clay.addWidget(self.sort)

        self.inner_first = QCheckBox("Innen vor Aussen")
        self.inner_first.setChecked(bool(defaults.get("inner_first", True)))
        self.inner_first.stateChanged.connect(self._refresh)
        clay.addWidget(self.inner_first)

        self.send_conditions = QCheckBox("Schneidbedingungen mitsenden")
        self.send_conditions.setToolTip(
            "Aus: der Plotter schneidet mit den Werten, die an seinem Bedienfeld eingestellt sind."
        )
        self.send_conditions.setChecked(bool(defaults.get("send_conditions", True)))
        clay.addWidget(self.send_conditions)

        side.addWidget(cond)

        view = QGroupBox("Vorschau")
        vlay = QVBoxLayout(view)
        self.arrows = QCheckBox("Richtungspfeile")
        self.arrows.stateChanged.connect(self._apply_view_options)
        vlay.addWidget(self.arrows)
        self.order = QCheckBox("Reihenfolge-Nummern")
        self.order.setChecked(True)
        self.order.stateChanged.connect(self._apply_view_options)
        vlay.addWidget(self.order)
        self.travel = QCheckBox("Leerfahrten (gelb)")
        self.travel.setChecked(True)
        self.travel.stateChanged.connect(self._apply_view_options)
        vlay.addWidget(self.travel)

        sim_row = QHBoxLayout()
        self.btn_sim = QPushButton("Simulation")
        self.btn_sim.setCheckable(True)
        self.btn_sim.toggled.connect(self._toggle_sim)
        sim_row.addWidget(self.btn_sim)
        self.sim_slider = QSlider(Qt.Horizontal)
        self.sim_slider.setRange(0, 100)
        self.sim_slider.setValue(100)
        self.sim_slider.valueChanged.connect(lambda v: self.preview.set_sim_progress(v / 100.0))
        sim_row.addWidget(self.sim_slider)
        vlay.addLayout(sim_row)
        vlay.addLayout(view_buttons(self.preview))
        side.addWidget(view)

        self.info = QLabel("")
        self.info.setWordWrap(True)
        side.addWidget(self.info)
        side.addStretch(1)

        self.btn_plot = QPushButton("Plot (senden)")
        self.btn_plot.clicked.connect(self._on_plot)
        side.addWidget(self.btn_plot)

        btn_save = QPushButton("In Datei speichern (.plt)")
        btn_save.clicked.connect(self._on_save_file)
        side.addWidget(btn_save)

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        side.addWidget(btn_cancel)

        self._refresh()
        self._apply_view_options()

    # -- Auftrag aufbauen --------------------------------------------------

    def _build_job(self) -> g.CutJob:
        return g.prepare_job(
            self.source,
            rotate_deg=0.0,
            mirror=False,
            overcut_mm=self.overcut.value(),
            sort=self.sort.isChecked(),
            inner_first=self.inner_first.isChecked(),
        )

    def _refresh(self) -> None:
        job = self._build_job()
        self.preview.set_data(job.polylines, self.sheet_width_mm, refit=self._first_refresh)
        self._first_refresh = False
        self.info.setText(
            f"Pfade: {len(job.polylines)}\n"
            f"Schnittlaenge: {job.total_cut_mm / 10.0:.1f} cm\n"
            f"Kopien: {self.copies}"
        )

    def _apply_view_options(self) -> None:
        self.preview.set_options(
            arrows=self.arrows.isChecked(),
            order=self.order.isChecked(),
            travel=self.travel.isChecked(),
        )

    # -- Simulation --------------------------------------------------------

    def _toggle_sim(self, on: bool) -> None:
        if on:
            self.preview.set_sim_progress(0.0)
            self.sim_slider.setValue(0)
            self._sim_timer.start(40)
        else:
            self._sim_timer.stop()
            self.preview.set_sim_progress(1.0)
            self.sim_slider.setValue(100)

    def _advance_sim(self) -> None:
        val = min(100, self.sim_slider.value() + 2)
        self.sim_slider.setValue(val)
        if val >= 100:
            self._sim_timer.stop()
            self.btn_sim.setChecked(False)

    # -- Ausgabe -----------------------------------------------------------

    def _generate_bytes(self) -> bytes:
        job = self._build_job()
        plotter = self.controller.profile["plotter"]
        condition = mgl.CutCondition(
            tool=1,
            speed=self.speed.value(),
            pressure=self.pressure.value(),
            offset=self.offset.value(),
        )
        return mgl.generate_bytes(
            job,
            conditions_by_color=self.controller.conditions_by_color(),
            default_condition=condition,
            options=mgl.PlotOptions(
                language=plotter.get("language", "mgl2"),
                emit_conditions=self.send_conditions.isChecked(),
            ),
            copies=self.copies,
        )

    def _on_plot(self) -> None:
        self._persist_defaults()
        data = self._generate_bytes()
        transport = build_transport(self.controller.profile["transport"])
        try:
            transport.send(data)
        except TransportError as exc:
            QMessageBox.critical(self, "Senden fehlgeschlagen", str(exc))
            return
        QMessageBox.information(
            self, "Plot", f"Gesendet an {transport.describe()} ({len(data)} Bytes)."
        )
        self.accept()

    def _on_save_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(self, "Plotdatei speichern", "out.plt", "Plot (*.plt)")
        if not path:
            return
        self._persist_defaults()
        data = self._generate_bytes()
        try:
            with open(path, "wb") as fh:
                fh.write(data)
        except OSError as exc:
            QMessageBox.critical(self, "Fehler", str(exc))
            return
        QMessageBox.information(self, "Gespeichert", f"{len(data)} Bytes nach {path}.")

    def _persist_defaults(self) -> None:
        self.controller.profile["defaults"].update(
            {
                "speed": self.speed.value(),
                "pressure": self.pressure.value(),
                "offset": self.offset.value(),
                "overcut_mm": self.overcut.value(),
                "sort": self.sort.isChecked(),
                "inner_first": self.inner_first.isChecked(),
                "send_conditions": self.send_conditions.isChecked(),
            }
        )
        self.controller.save()
