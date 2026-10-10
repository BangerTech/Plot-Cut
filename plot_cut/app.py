"""Verbindet GUI, Steuerkanal, Geometrie und Transport zu einer Anwendung."""

from __future__ import annotations

import time

from PySide6.QtWidgets import QMessageBox

from . import geometry as g
from . import settings as settings_mod
from . import vc_launcher
from .mgl import CutCondition
from .vc_control import VcControlClient, VcControlError


class AppController:
    """Haelt den Zustand und reagiert auf die Panel-Knoepfe."""

    def __init__(self) -> None:
        self.settings = settings_mod.load_settings()
        ctrl = self.settings.get("control", {})
        self.vc = VcControlClient(
            host=ctrl.get("host", "127.0.0.1"), port=int(ctrl.get("port", 7979))
        )
        self.panel = None  # wird von main gesetzt

    # -- Persistenz --------------------------------------------------------

    def save(self) -> None:
        settings_mod.save_settings(self.settings)

    @property
    def profile_name(self) -> str:
        settings_mod.active_profile(self.settings)
        return self.settings["active_profile"]

    @property
    def profile(self) -> dict:
        """Das aktive Plotter-Profil (plotter, transport, defaults, conditions_by_color)."""
        return settings_mod.active_profile(self.settings)

    def profile_names(self) -> list[str]:
        return list(self.settings["profiles"].keys())

    def switch_profile(self, name: str) -> None:
        if name in self.settings["profiles"] and name != self.settings.get("active_profile"):
            self.settings["active_profile"] = name
            self.save()
            self._status(f"Plotter: {name}")

    def conditions_by_color(self) -> dict[str, CutCondition]:
        return settings_mod.conditions_by_color(self.profile)

    def default_condition(self) -> CutCondition:
        return settings_mod.default_condition(self.profile)

    def per_file_settings(self, document_path: str | None) -> dict:
        return settings_mod.get_per_file(self.settings, document_path)

    def store_per_file(self, document_path: str | None, values: dict) -> None:
        existing = settings_mod.get_per_file(self.settings, document_path)
        existing.update(values)
        settings_mod.set_per_file(self.settings, document_path, existing)
        self.save()

    def save_panel_geometry(self) -> None:
        if self.panel is None:
            return
        geo = self.panel.geometry()
        self.settings.setdefault("ui", {})["panel_pos"] = [geo.x(), geo.y()]
        self.save()

    def restore_panel_geometry(self) -> None:
        if self.panel is None:
            return
        pos = self.settings.get("ui", {}).get("panel_pos")
        if isinstance(pos, list) and len(pos) == 2:
            self.panel.move(int(pos[0]), int(pos[1]))

    # -- Statusanzeige -----------------------------------------------------

    def _status(self, text: str) -> None:
        if self.panel is not None:
            self.panel.set_status(text)

    # -- VectorCraft-Steuerkanal sicherstellen -----------------------------

    def ensure_control_channel(self, prompt: bool = True) -> bool:
        """Stellt sicher, dass der Steuerkanal offen ist.

        Ist er zu, wird VectorCraft (falls gefunden) nach Rueckfrage mit
        ``--control <port>`` gestartet. Gibt True zurueck, wenn der Kanal am
        Ende erreichbar ist.
        """
        if vc_launcher.control_port_open(self.vc.host, self.vc.port):
            return True

        ctrl = self.settings.get("control", {})
        exe = vc_launcher.find_vectorcraft(ctrl.get("vectorcraft_exe") or None)
        if exe:
            # Pfad fuer spaeter merken.
            self.settings.setdefault("control", {})["vectorcraft_exe"] = exe
            self.save()

        if not exe:
            if prompt:
                QMessageBox.warning(
                    self.panel,
                    "Steuerkanal nicht aktiv",
                    "VectorCraft wurde nicht gefunden. Bitte einmal im Setup den "
                    "Pfad zu vectorcraft.exe angeben.\n\n"
                    "Der Steuerkanal (Port "
                    f"{self.vc.port}) muss aktiv sein, damit die Auswahl geholt "
                    "werden kann.",
                )
            return False

        if prompt:
            answer = QMessageBox.question(
                self.panel,
                "VectorCraft neu starten?",
                "Der VectorCraft-Steuerkanal ist nicht aktiv.\n\n"
                "Damit das Panel die Auswahl holen kann, muss VectorCraft mit "
                "aktivem Steuerkanal laufen.\n\n"
                "Jetzt VectorCraft mit Steuerkanal starten?\n"
                "(Bitte vorher ungespeicherte Arbeit in einem evtl. offenen "
                "VectorCraft sichern.)",
            )
            if answer != QMessageBox.Yes:
                return False

        self._status("Starte VectorCraft ...")
        if not vc_launcher.launch_with_control(exe, self.vc.port):
            QMessageBox.critical(
                self.panel, "Start fehlgeschlagen", f"VectorCraft ({exe}) ließ sich nicht starten."
            )
            return False

        # Auf das Hochfahren warten (bis zu ~20 s).
        for _ in range(40):
            if vc_launcher.control_port_open(self.vc.host, self.vc.port):
                self._status("Steuerkanal aktiv")
                return True
            time.sleep(0.5)

        self._status("Steuerkanal kam nicht hoch")
        return False

    # -- Panel-Aktionen ----------------------------------------------------

    def on_plot(self) -> None:
        if not self.ensure_control_channel():
            self._status("Steuerkanal nicht aktiv")
            return
        self._status("Hole Auswahl ...")
        try:
            selection = self.vc.export_selection()
        except VcControlError as exc:
            self._status("Fehler")
            QMessageBox.warning(
                self.panel,
                "Keine Auswahl",
                "Die Auswahl konnte nicht geholt werden.\n\n"
                f"{exc}\n\nLaeuft VectorCraft mit '--control "
                f"{self.vc.port}' und ist etwas ausgewaehlt?",
            )
            return

        if selection.count == 0:
            # Manche Versionen liefern keinen Zaehler; nur hinweisen, nicht abbrechen.
            self._status("Hinweis: evtl. nichts ausgewaehlt")

        try:
            polylines = g.polylines_from_bytes(selection.data, selection.fmt)
        except Exception as exc:  # defensiv: Parserfehler nicht durchreichen
            self._status("Fehler beim Lesen")
            QMessageBox.critical(self.panel, "Importfehler", str(exc))
            return

        if not polylines:
            self._status("Keine Pfade")
            QMessageBox.information(
                self.panel,
                "Keine Schneidepfade",
                "In der Auswahl wurden keine Linien/Pfade gefunden.",
            )
            return

        self._status(f"{len(polylines)} Pfade geladen")
        from .ui.plot_dialog import PlotDialog

        dlg = PlotDialog(self, polylines, selection.document_path)
        dlg.exec()
        self._status("Bereit")

    def on_setup(self) -> None:
        from .ui.setup_dialog import SetupDialog

        dlg = SetupDialog(self)
        dlg.exec()
        # Steuerkanal-Client neu aufbauen (Port koennte sich geaendert haben).
        ctrl = self.settings.get("control", {})
        self.vc = VcControlClient(
            host=ctrl.get("host", "127.0.0.1"), port=int(ctrl.get("port", 7979))
        )
        if self.panel is not None:
            self.panel.reload_profiles()
        self._status(f"Plotter: {self.profile_name}")

    def on_test_connection(self) -> None:
        from .transport import build_transport

        # Steuerkanal
        vc_ok = self.vc.ping()
        transport = build_transport(self.profile["transport"])
        tr_ok, tr_msg = transport.test()

        lines = [
            f"VectorCraft-Steuerkanal ({self.vc.host}:{self.vc.port}): "
            + ("OK" if vc_ok else "nicht erreichbar"),
            f"{self.profile_name} ({transport.describe()}): " + ("OK" if tr_ok else "Fehler"),
            tr_msg,
        ]
        QMessageBox.information(self.panel, "Verbindungstest", "\n".join(lines))
        self._status("Test abgeschlossen")

    def show_info(self) -> None:
        from . import __version__

        QMessageBox.information(
            self.panel,
            "Plot Cut",
            f"Plot Cut v{__version__}\n\n"
            "Schneide-Panel fuer VectorCraft, steuert mehrere Plotter\n"
            "(z. B. Mimaki, Vevor) ueber den Loki-PrintServer.\n\n"
            "FineCut ist eine Marke von Mimaki; dieses Projekt ist unabhaengig.",
        )
