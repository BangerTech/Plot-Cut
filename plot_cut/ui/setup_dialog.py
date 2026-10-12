"""Plotter/User-Setup: Profile, VectorCraft, Plotter, Verbindung, Bedingungen, Favoriten."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import i18n
from .. import mgl
from .. import settings as settings_mod
from ..transport import LokiTransport, TransportError, build_transport
from .popup import information, question, warning
from .style import FINECUT_STYLE, ComboBox

if TYPE_CHECKING:
    from ..app import AppController

TRANSPORT_KINDS = [
    ("loki", "Loki-Server (USB-Bridge)"),
    ("tcp", "TCP roh (socat / Port 9100)"),
    ("serial", "COM-Port"),
    ("file", "Datei (.plt, zum Testen)"),
    ("mimaki_usb", "Mimaki USB (lokal, wie FineCut)"),
]


class SetupDialog(QDialog):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        # Auf einer Kopie arbeiten; erst "Speichern" uebernimmt die Aenderungen.
        self.work = copy.deepcopy(controller.settings)
        settings_mod.active_profile(self.work)
        self.current: str = self.work["active_profile"]

        i18n.bind(self, window="Plotter / User Setup")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(FINECUT_STYLE)
        self.resize(500, 680)
        self._ui_lang_before = i18n.language()

        root = QVBoxLayout(self)
        root.addWidget(self._build_language_box())
        root.addWidget(self._build_vc_box())
        root.addWidget(self._build_profile_box())
        root.addWidget(self._build_plotter_box())
        root.addWidget(self._build_connection_box())
        root.addWidget(self._build_condition_box())
        root.addWidget(self._build_favorites_box())

        btns = QHBoxLayout()
        ok = QPushButton()
        i18n.bind(ok, text="Speichern")
        ok.clicked.connect(self._on_ok)
        btns.addWidget(ok)
        cancel = QPushButton()
        i18n.bind(cancel, text="Abbrechen")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        root.addLayout(btns)

        self._reload_profile_combo()
        self._load_form(self.current)
        i18n.watch(self)

    def _build_language_box(self) -> QGroupBox:
        box = QGroupBox()
        i18n.bind(box, title="Oberfläche")
        row = QHBoxLayout(box)
        self.ui_language = ComboBox()
        i18n.bind_items(self.ui_language, [("Deutsch", "de"), ("English", "en")])
        current = str(self.work.get("ui", {}).get("language", "de"))
        index = max(0, self.ui_language.findData(current))
        self.ui_language.setCurrentIndex(index)
        self.ui_language.currentIndexChanged.connect(self._on_ui_language)
        row.addWidget(self.ui_language, 1)
        hint = i18n.lab(
            "Deutsch oder English. Das Panel wechselt sofort, dieses Fenster ebenfalls.",
            wrap=True,
        )
        row.addWidget(hint, 2)
        return box

    def _on_ui_language(self) -> None:
        lang = str(self.ui_language.currentData() or "de")
        self.work.setdefault("ui", {})["language"] = lang
        i18n.set_language(lang)

    def reject(self) -> None:  # noqa: N802
        i18n.set_language(self._ui_lang_before)
        super().reject()

    # -- Aufbau ------------------------------------------------------------

    def _build_vc_box(self) -> QGroupBox:
        box = QGroupBox()
        i18n.bind(box, title="VectorCraft (Steuerkanal)")
        form = QFormLayout(box)
        ctrl = self.work.get("control", {})
        self.vc_exe = QLineEdit(ctrl.get("vectorcraft_exe", ""))
        i18n.bind(self.vc_exe, placeholder="automatisch gesucht, falls leer")
        row = QHBoxLayout()
        row.addWidget(self.vc_exe, 1)
        browse = QPushButton("...")
        browse.setFixedWidth(32)
        browse.clicked.connect(self._browse_vc_exe)
        row.addWidget(browse)
        wrap = QWidget()
        wrap.setLayout(row)
        form.addRow("vectorcraft.exe", wrap)
        self.vc_port = QSpinBox()
        self.vc_port.setRange(1, 65535)
        self.vc_port.setValue(int(ctrl.get("port", 7979)))
        form.addRow(i18n.lab("Steuerkanal-Port"), self.vc_port)
        return box

    def _build_profile_box(self) -> QGroupBox:
        box = QGroupBox()
        i18n.bind(box, title="Plotter-Profil")
        lay = QHBoxLayout(box)
        self.profile_combo = ComboBox()
        self.profile_combo.currentTextChanged.connect(self._on_profile_selected)
        lay.addWidget(self.profile_combo, 1)
        for text, slot in (
            ("Neu ...", self._new_profile),
            ("Umbenennen ...", self._rename_profile),
            ("Loeschen", self._delete_profile),
        ):
            btn = QPushButton()
            i18n.bind(btn, text=text)
            btn.clicked.connect(slot)
            lay.addWidget(btn)
        return box

    def _build_plotter_box(self) -> QGroupBox:
        box = QGroupBox()
        i18n.bind(box, title="Plotter")
        form = QFormLayout(box)
        self.model = QLineEdit()
        form.addRow(i18n.lab("Modell"), self.model)
        self.language = ComboBox()
        i18n.bind_items(
            self.language,
            [
                ("MGL-IIc (Mimaki)", "mgl2"),
                ("HP-GL (z. B. Vevor)", "hpgl"),
                ("DMPL", "dmpl"),
            ],
        )
        self.language.currentIndexChanged.connect(self._on_language_changed)
        form.addRow(i18n.lab("Befehlssprache"), self.language)
        self.sheet_width = QDoubleSpinBox()
        self.sheet_width.setRange(10.0, 5000.0)
        form.addRow(i18n.lab("Folienbreite (mm)"), self.sheet_width)
        self.sheet_height = QDoubleSpinBox()
        self.sheet_height.setRange(10.0, 100000.0)
        form.addRow(i18n.lab("Folienlänge (mm)"), self.sheet_height)
        self.step_mm = ComboBox()
        form.addRow(i18n.lab("Auflösung"), self.step_mm)
        self.crv_res = QDoubleSpinBox()
        self.crv_res.setRange(0.01, 2.0)
        self.crv_res.setSingleStep(0.01)
        self.crv_res.setDecimals(2)
        form.addRow(i18n.lab("Kurvenauflösung (mm)"), self.crv_res)
        return box

    def _build_connection_box(self) -> QGroupBox:
        box = QGroupBox()
        i18n.bind(box, title="Verbindung")
        lay = QVBoxLayout(box)
        row = QHBoxLayout()
        row.addWidget(i18n.lab("Art"))
        self.kind = ComboBox()
        i18n.bind_items(self.kind, [(label, key) for key, label in TRANSPORT_KINDS])
        self.kind.currentIndexChanged.connect(lambda i: self.stack.setCurrentIndex(i))
        row.addWidget(self.kind, 1)
        lay.addLayout(row)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_loki_page())
        self.stack.addWidget(self._build_tcp_page())
        self.stack.addWidget(self._build_serial_page())
        self.stack.addWidget(self._build_file_page())
        self.stack.addWidget(self._build_mimaki_usb_page())
        lay.addWidget(self.stack)

        test_btn = QPushButton()
        i18n.bind(test_btn, text="Verbindung testen")
        test_btn.clicked.connect(self._on_test)
        lay.addWidget(test_btn)
        return box

    def _build_loki_page(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.loki_host = QLineEdit()
        form.addRow(i18n.lab("Loki-Server (IP)"), self.loki_host)
        self.loki_port = QSpinBox()
        self.loki_port.setRange(1, 65535)
        form.addRow(i18n.lab("Port"), self.loki_port)
        dev_row = QHBoxLayout()
        self.loki_device = ComboBox()
        self.loki_device.setEditable(True)
        dev_row.addWidget(self.loki_device, 1)
        fetch = QPushButton()
        i18n.bind(fetch, text="Geraete laden")
        fetch.clicked.connect(self._fetch_loki_devices)
        dev_row.addWidget(fetch)
        wrap = QWidget()
        wrap.setLayout(dev_row)
        form.addRow(i18n.lab("Geraet"), wrap)
        return w

    def _build_tcp_page(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.tcp_host = QLineEdit()
        form.addRow(i18n.lab("Host"), self.tcp_host)
        self.tcp_port = QSpinBox()
        self.tcp_port.setRange(1, 65535)
        form.addRow(i18n.lab("Port"), self.tcp_port)
        return w

    def _build_serial_page(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.serial_port = QLineEdit()
        i18n.bind(
            self.serial_port,
            placeholder="z. B. COM5 oder auto",
            tip="auto = CH340-Plotter (z. B. Vevor) selbst finden, direkt am PC oder per Loki-Client",
        )
        form.addRow(i18n.lab("COM-Port"), self.serial_port)
        self.baud = QSpinBox()
        self.baud.setRange(300, 921600)
        form.addRow(i18n.lab("Baudrate"), self.baud)
        return w

    def _build_file_page(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.file_path = QLineEdit()
        form.addRow(i18n.lab("Dateipfad"), self.file_path)
        return w

    def _build_mimaki_usb_page(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.addRow(i18n.lab(
            "Schreibt wie FineCut an den Mimaki-USB-Treiber. Der Cutter kann direkt an diesem PC stecken "
            "oder vom Loki-Client per USB/IP angehängt sein. Leer lassen sucht den Treiber selbst.",
            wrap=True,
        ))
        self.usb_path = QLineEdit()
        i18n.bind(self.usb_path, placeholder="leer = automatisch finden")
        form.addRow(i18n.lab("Geraetepfad"), self.usb_path)
        return w

    def _build_condition_box(self) -> QGroupBox:
        box = QGroupBox()
        i18n.bind(box, title="Standard-Schneidbedingung")
        form = QFormLayout(box)
        self.speed = QSpinBox()
        self.speed.setRange(1, 120)
        form.addRow(i18n.lab("Geschwindigkeit (cm/s)"), self.speed)
        self.pressure = QSpinBox()
        self.pressure.setRange(1, 500)
        form.addRow(i18n.lab("Druck (g)"), self.pressure)
        self.offset = QDoubleSpinBox()
        self.offset.setRange(0.0, 2.0)
        self.offset.setSingleStep(0.05)
        form.addRow(i18n.lab("Klingenoffset (mm)"), self.offset)
        return box

    def _build_favorites_box(self) -> QGroupBox:
        box = QGroupBox()
        i18n.bind(box, title="Favoriten (Schneidbedingungen)")
        lay = QHBoxLayout(box)
        self.fav_combo = ComboBox()
        self._reload_favorites()
        lay.addWidget(self.fav_combo, 1)
        load_btn = QPushButton()
        i18n.bind(load_btn, text="Laden")
        load_btn.clicked.connect(self._load_favorite)
        lay.addWidget(load_btn)
        save_btn = QPushButton()
        i18n.bind(save_btn, text="Speichern als ...")
        save_btn.clicked.connect(self._save_favorite)
        lay.addWidget(save_btn)
        return box

    # -- Formular <-> Profil -------------------------------------------------

    def _load_form(self, name: str) -> None:
        prof = self.work["profiles"][name]
        p, t, d = prof["plotter"], prof["transport"], prof["defaults"]
        self.model.setText(p.get("model", ""))
        lang = p.get("language", "mgl2")
        self.language.setCurrentIndex(max(0, self.language.findData(lang)))
        self.sheet_width.setValue(float(p.get("sheet_width_mm", 610.0)))
        self.sheet_height.setValue(float(p.get("sheet_height_mm", 1000.0)))
        self.crv_res.setValue(float(p.get("crv_res", 0.05)))
        self._fill_step_combo(lang, float(p.get("step_mm", 0.025)))
        self._apply_condition_limits(lang)

        self.kind.setCurrentIndex(max(0, self.kind.findData(t.get("kind", "file"))))
        self.stack.setCurrentIndex(self.kind.currentIndex())
        self.loki_host.setText(t.get("host", ""))
        self.loki_port.setValue(int(t.get("loki_port", 7576)))
        self.loki_device.clear()
        if t.get("device"):
            self.loki_device.addItem(t["device"], t["device"])
        self.loki_device.setCurrentText(t.get("device", ""))
        self.tcp_host.setText(t.get("host", ""))
        self.tcp_port.setValue(int(t.get("port", 7580)))
        self.serial_port.setText(t.get("serial_port", "COM3"))
        self.baud.setValue(int(t.get("baud", 9600)))
        self.file_path.setText(t.get("file_path", "out.plt"))
        self.usb_path.setText(t.get("usb_path", ""))

        self.speed.setValue(int(d.get("speed", 30)))
        self.pressure.setValue(int(d.get("pressure", 100)))
        self.offset.setValue(float(d.get("offset", 0.3)))

    def _store_form(self, name: str) -> None:
        prof = self.work["profiles"].get(name)
        if prof is None:
            return
        prof["plotter"].update(
            {
                "model": self.model.text().strip(),
                "language": self.language.currentData(),
                "sheet_width_mm": self.sheet_width.value(),
                "sheet_height_mm": self.sheet_height.value(),
                "step_mm": float(self.step_mm.currentData() or 0.025),
                "crv_res": self.crv_res.value(),
            }
        )
        prof["transport"] = self._collect_transport()
        prof["defaults"].update(
            {
                "speed": self.speed.value(),
                "pressure": self.pressure.value(),
                "offset": self.offset.value(),
            }
        )

    def _on_language_changed(self) -> None:
        lang = str(self.language.currentData() or "mgl2")
        current = float(self.step_mm.currentData() or 0.025) if self.step_mm.count() else 0.025
        self._fill_step_combo(lang, current)
        self._apply_condition_limits(lang)

    def _fill_step_combo(self, language: str, selected: float) -> None:
        self.step_mm.blockSignals(True)
        self.step_mm.clear()
        for value, label in mgl.step_choices(language):
            self.step_mm.addItem(label, value)
        idx = 0
        for i in range(self.step_mm.count()):
            if abs(float(self.step_mm.itemData(i)) - selected) < 1e-9:
                idx = i
                break
        self.step_mm.setCurrentIndex(idx)
        self.step_mm.blockSignals(False)

    def _apply_condition_limits(self, language: str) -> None:
        lo, hi = mgl.speed_range(language)
        self.speed.setRange(lo, hi)
        lo, hi = mgl.pressure_range(language)
        self.pressure.setRange(lo, hi)

    def _collect_transport(self) -> dict:
        kind = self.kind.currentData()
        host = self.loki_host.text().strip() if kind == "loki" else self.tcp_host.text().strip()
        device = self.loki_device.currentData() or self.loki_device.currentText().strip()
        return {
            "kind": kind,
            "host": host,
            "loki_port": self.loki_port.value(),
            "device": device,
            "port": self.tcp_port.value(),
            "serial_port": self.serial_port.text().strip(),
            "baud": self.baud.value(),
            "file_path": self.file_path.text().strip(),
            "usb_path": self.usb_path.text().strip(),
        }

    # -- Profile verwalten -------------------------------------------------

    def _reload_profile_combo(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(list(self.work["profiles"].keys()))
        self.profile_combo.setCurrentText(self.current)
        self.profile_combo.blockSignals(False)

    def _on_profile_selected(self, name: str) -> None:
        if not name or name == self.current:
            return
        self._store_form(self.current)
        self.current = name
        self._load_form(name)

    def _new_profile(self) -> None:
        name, ok = QInputDialog.getText(self, i18n.tr("Neuer Plotter"), i18n.tr("Name des Plotters:"))
        name = name.strip()
        if not ok or not name:
            return
        if name in self.work["profiles"]:
            warning(self, "Neuer Plotter", i18n.trf("'{name}' gibt es schon.", name=name))
            return
        self._store_form(self.current)
        settings_mod.new_profile(self.work, name, copy_from=self.current)
        self.current = name
        self._reload_profile_combo()
        self._load_form(name)

    def _rename_profile(self) -> None:
        new, ok = QInputDialog.getText(self, i18n.tr("Umbenennen"), i18n.tr("Neuer Name:"), text=self.current)
        new = new.strip()
        if not ok or not new or new == self.current:
            return
        self._store_form(self.current)
        if not settings_mod.rename_profile(self.work, self.current, new):
            warning(self, "Umbenennen", i18n.trf("'{name}' ist schon vergeben.", name=new))
            return
        self.current = new
        self._reload_profile_combo()

    def _delete_profile(self) -> None:
        if len(self.work["profiles"]) <= 1:
            information(self, "Loeschen", "Mindestens ein Plotter muss bleiben.")
            return
        if not question(self, "Loeschen", i18n.trf("Plotter '{name}' löschen?", name=self.current)):
            return
        settings_mod.delete_profile(self.work, self.current)
        self.current = self.work["active_profile"]
        self._reload_profile_combo()
        self._load_form(self.current)

    # -- Aktionen ----------------------------------------------------------

    def _browse_vc_exe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, i18n.tr("vectorcraft.exe wählen"), "C:\\Program Files\\VectorCraft", i18n.tr("Programme (*.exe)")
        )
        if path:
            self.vc_exe.setText(path)

    def _fetch_loki_devices(self) -> None:
        loki = LokiTransport(host=self.loki_host.text().strip(), port=self.loki_port.value())
        try:
            devices = loki.list_devices()
        except TransportError as exc:
            warning(self, "Loki", str(exc))
            return
        current = self.loki_device.currentData() or self.loki_device.currentText()
        self.loki_device.clear()
        for dev in devices:
            label = f"{dev.name} ({dev.id})" + ("" if dev.available else i18n.tr(" - belegt"))
            self.loki_device.addItem(label, dev.id)
        idx = self.loki_device.findData(current)
        if idx >= 0:
            self.loki_device.setCurrentIndex(idx)
        if not devices:
            information(self, "Loki", i18n.tr("Loki meldet keine Plotter."))

    def _on_test(self) -> None:
        ok, msg = build_transport(self._collect_transport()).test()
        (information if ok else warning)(self, "Verbindung", i18n.tr(msg))

    def _reload_favorites(self) -> None:
        self.fav_combo.clear()
        self.fav_combo.addItems(sorted(self.work.get("favorites", {}).keys()))

    def _load_favorite(self) -> None:
        fav = self.work.get("favorites", {}).get(self.fav_combo.currentText())
        if not fav:
            return
        self.speed.setValue(int(fav.get("speed", 30)))
        self.pressure.setValue(int(fav.get("pressure", 100)))
        self.offset.setValue(float(fav.get("offset", 0.3)))

    def _save_favorite(self) -> None:
        name, ok = QInputDialog.getText(self, i18n.tr("Favorit speichern"), i18n.tr("Name:"))
        name = name.strip()
        if not ok or not name:
            return
        self.work.setdefault("favorites", {})[name] = {
            "speed": self.speed.value(),
            "pressure": self.pressure.value(),
            "offset": self.offset.value(),
        }
        self._reload_favorites()
        self.fav_combo.setCurrentText(name)

    def _on_ok(self) -> None:
        self._store_form(self.current)
        self.work.setdefault("control", {}).update(
            {"vectorcraft_exe": self.vc_exe.text().strip(), "port": self.vc_port.value()}
        )
        self.work["active_profile"] = self.current
        self.controller.settings.clear()
        self.controller.settings.update(self.work)
        self.controller.save()
        self.accept()
