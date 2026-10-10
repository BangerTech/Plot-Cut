"""[Plot]-Fenster: Folienvorschau, Position, Drehen, Spiegeln, Kopien."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .. import geometry as g
from .plot_out_dialog import PlotOutDialog
from .preview import PreviewWidget, view_buttons

if TYPE_CHECKING:
    from ..app import AppController


class PlotDialog(QDialog):
    def __init__(
        self,
        controller: AppController,
        polylines: list[g.Polyline],
        document_path: str | None,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.source = polylines
        self.document_path = document_path

        self.setWindowTitle(f"Plot - {controller.profile_name}")
        self.resize(900, 600)

        per_file = controller.per_file_settings(document_path)

        root = QHBoxLayout(self)
        self.preview = PreviewWidget(mode="plot")
        root.addWidget(self.preview, 3)

        side = QVBoxLayout()
        root.addLayout(side, 1)

        side.addWidget(QLabel("Folienbreite (mm)"))
        self.sheet_width = QDoubleSpinBox()
        self.sheet_width.setRange(10.0, 5000.0)
        self.sheet_width.setValue(controller.profile["plotter"].get("sheet_width_mm", 610.0))
        self.sheet_width.valueChanged.connect(self._refresh)
        side.addWidget(self.sheet_width)

        side.addWidget(QLabel("Drehen"))
        self.rotate = QComboBox()
        self.rotate.addItems(["0 Grad", "90 Grad", "180 Grad", "270 Grad"])
        self.rotate.setCurrentIndex(int(per_file.get("rotate_index", 0)))
        self.rotate.currentIndexChanged.connect(self._refresh)
        side.addWidget(self.rotate)

        self.mirror = QCheckBox("Spiegeln")
        self.mirror.setChecked(bool(per_file.get("mirror", False)))
        self.mirror.stateChanged.connect(self._refresh)
        side.addWidget(self.mirror)

        side.addWidget(QLabel("Kopien"))
        self.copies = QSpinBox()
        self.copies.setRange(1, 999)
        self.copies.setValue(int(per_file.get("copies", 1)))
        side.addWidget(self.copies)

        self.info = QLabel("")
        self.info.setWordWrap(True)
        side.addWidget(self.info)

        side.addLayout(view_buttons(self.preview))
        side.addStretch(1)

        self.btn_plot_out = QPushButton("Plot Out ...")
        self.btn_plot_out.clicked.connect(self._open_plot_out)
        side.addWidget(self.btn_plot_out)

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        side.addWidget(btn_cancel)

        self._refresh()

    # -- Logik -------------------------------------------------------------

    def _rotate_degrees(self) -> float:
        return [0.0, 90.0, 180.0, 270.0][self.rotate.currentIndex()]

    def _transformed(self) -> list[g.Polyline]:
        work = self.source
        deg = self._rotate_degrees()
        if deg:
            work = g.rotate(work, deg)
        if self.mirror.isChecked():
            work = g.mirror_x(work)
        work = g.move_to_origin(work, margin=0.0)
        return work

    def _refresh(self) -> None:
        work = self._transformed()
        self.preview.set_data(work, self.sheet_width.value())
        minx, miny, maxx, maxy = g.bounds_of(work)
        w = maxx - minx
        h = maxy - miny
        closed = sum(1 for pl in work if pl.closed)
        over = ""
        if w > self.sheet_width.value():
            over = "\n\nWarnung: breiter als die Folie!"
        self.info.setText(
            f"Groesse: {w:.1f} x {h:.1f} mm\n"
            f"Schnittpfade: {len(work)} ({closed} geschlossen){over}"
        )

    def _open_plot_out(self) -> None:
        self.controller.store_per_file(
            self.document_path,
            {
                "rotate_index": self.rotate.currentIndex(),
                "mirror": self.mirror.isChecked(),
                "copies": self.copies.value(),
            },
        )
        dlg = PlotOutDialog(
            self.controller,
            source=self._transformed(),
            sheet_width_mm=self.sheet_width.value(),
            copies=self.copies.value(),
            document_path=self.document_path,
        )
        dlg.setWindowModality(Qt.ApplicationModal)
        if dlg.exec() == QDialog.Accepted:
            self.accept()
