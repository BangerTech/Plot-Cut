"""Verbindet GUI, Steuerkanal, Geometrie und Transport zu einer Anwendung."""

from __future__ import annotations

import math
import re
import time
import xml.etree.ElementTree as ET

from .ui import popup

from . import geometry as g
from . import i18n
from . import settings as settings_mod
from . import vc_launcher
from .mgl import CutCondition
from .vc_control import VcControlClient, VcControlError


def _svg_has_text(data: bytes) -> bool:
    return b"<text" in data.lower()


def _transform_scale(transform: str | None) -> tuple[float, float]:
    """Skalierung aus einem SVG-transform. Stroke-Breite wird damit mitvergroessert."""
    if not transform:
        return 1.0, 1.0
    sx = sy = 1.0
    for a, b, c, d in re.findall(
        r"matrix\(\s*([-\d.eE]+)[\s,]+([-\d.eE]+)[\s,]+([-\d.eE]+)[\s,]+([-\d.eE]+)",
        transform,
    ):
        sx *= math.hypot(float(a), float(b))
        sy *= math.hypot(float(c), float(d))
    for match in re.finditer(r"scale\(\s*([-\d.eE]+)(?:[\s,]+([-\d.eE]+))?", transform):
        x = abs(float(match.group(1)))
        y = abs(float(match.group(2) or match.group(1)))
        sx *= x
        sy *= y
    return sx, sy


def _length_pt(value: str | None) -> float:
    if not value:
        return 0.0
    match = re.match(r"\s*([-\d.eE]+)", value)
    return float(match.group(1)) if match else 0.0


def _outward_stroke_pt(data: bytes, align: str) -> float:
    """Wie weit die aeusserste Kante ausserhalb des Pfads liegt, in Dokument-Punkten.

    Ein Strich in VectorCraft macht den Buchstaben breiter. ``center`` zaehlt halb,
    ``outside`` ganz, ``inside`` gar nicht, weil die Aussenkante dann der Pfad selbst ist.
    Die SVG-Breite steht vor der Text-Skalierung, darum wird die Matrix mitgerechnet.
    """
    if align == "inside":
        return 0.0
    try:
        root = ET.fromstring(data.decode("utf-8", errors="replace"))
    except ET.ParseError:
        return 0.0
    parent = {child: el for el in root.iter() for child in list(el)}
    best = 0.0
    for el in root.iter():
        width = _length_pt(el.get("stroke-width"))
        style = el.get("style") or ""
        if width <= 0 and "stroke-width" in style:
            found = re.search(r"stroke-width\s*:\s*([^;]+)", style)
            width = _length_pt(found.group(1) if found else None)
        if width <= 0:
            continue
        stroke = (el.get("stroke") or "").strip().lower()
        if not stroke and "stroke" in style:
            found = re.search(r"(?:^|;)\s*stroke\s*:\s*([^;]+)", style)
            stroke = (found.group(1) if found else "").strip().lower()
        if stroke in ("", "none", "transparent"):
            continue
        sx, sy = 1.0, 1.0
        cur: ET.Element | None = el
        while cur is not None:
            lsx, lsy = _transform_scale(cur.get("transform"))
            sx *= lsx
            sy *= lsy
            cur = parent.get(cur)
        best = max(best, width * (abs(sx) + abs(sy)) / 2.0)
    if align == "outside":
        return best
    return best * 0.5


class AppController:
    """Haelt den Zustand und reagiert auf die Panel-Knoepfe."""

    def __init__(self) -> None:
        self.settings = settings_mod.load_settings()
        ctrl = self.settings.get("control", {})
        self.vc = VcControlClient(
            host=ctrl.get("host", "127.0.0.1"), port=int(ctrl.get("port", 7979))
        )
        i18n.set_language(str(self.settings.get("ui", {}).get("language", "de")))
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
            self._status("Plotter: {name}", name=name)

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

    def _status(self, text: str, **fmt: object) -> None:
        if self.panel is not None:
            self.panel.set_status(text, **fmt)

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
                popup.warning(
                    self.panel,
                    "Steuerkanal nicht aktiv",
                    i18n.trf(
                        "VectorCraft wurde nicht gefunden. Bitte einmal im Setup den Pfad zu vectorcraft.exe angeben.\n\n"
                        "Der Steuerkanal (Port {port}) ist nötig, damit die Auswahl gelesen werden kann.",
                        port=self.vc.port,
                    ),
                )
            return False

        if prompt:
            start = popup.question(
                self.panel,
                "VectorCraft neu starten?",
                "Der VectorCraft-Steuerkanal ist nicht aktiv.\n\n"
                "Damit das Panel die Auswahl holen kann, muss VectorCraft mit aktivem Steuerkanal laufen.\n\n"
                "Jetzt VectorCraft mit Steuerkanal starten?\n"
                "(Eine offene Zeichnung vorher in VectorCraft sichern.)",
            )
            if not start:
                return False

        self._status("Starte VectorCraft ...")
        if not vc_launcher.launch_with_control(exe, self.vc.port):
            popup.critical(
                self.panel,
                "Start fehlgeschlagen",
                i18n.trf("VectorCraft ({exe}) ließ sich nicht starten.", exe=exe),
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
            popup.warning(
                self.panel,
                "Keine Auswahl",
                i18n.trf(
                    "Die Auswahl konnte nicht geholt werden.\n\n{exc}\n\n"
                    "Läuft VectorCraft mit '--control {port}' und ist etwas ausgewählt?",
                    exc=exc,
                    port=self.vc.port,
                ),
            )
            return

        if selection.count == 0:
            # Manche Versionen liefern keinen Zaehler; nur hinweisen, nicht abbrechen.
            self._status("Hinweis: evtl. nichts ausgewaehlt")

        try:
            flatness = float(self.profile["plotter"].get("crv_res", g.DEFAULT_FLATNESS_MM))
            polylines = g.polylines_from_bytes(selection.data, selection.fmt, flatness=flatness)
        except Exception as exc:  # defensiv: Parserfehler nicht durchreichen
            self._status("Fehler beim Lesen")
            popup.critical(self.panel, "Importfehler", str(exc))
            return

        if not polylines:
            self._status("Keine Pfade")
            if _svg_has_text(selection.data):
                popup.information(
                    self.panel,
                    "Text statt Kontur",
                    "Die Auswahl ist Text, zum Beispiel ein Buchstabe.\n\n"
                    "Kontur wandelt ihn in eine Schnittlinie um, so wie FineCut. "
                    "Danach kann er geschnitten werden.",
                )
            else:
                popup.information(
                    self.panel,
                    "Keine Schneidepfade",
                    "In der Auswahl wurden keine Linien/Pfade gefunden.",
                )
            return

        self._status("{n} Pfade geladen", n=len(polylines))
        from .ui.plot_dialog import PlotDialog

        if self.panel is not None:
            self.panel.hide()
        try:
            dlg = PlotDialog(self, polylines, selection.document_path)
            dlg.exec()
        except Exception as exc:
            popup.critical(
                self.panel,
                "Plot",
                i18n.trf("Das Plot-Fenster konnte nicht geoeffnet werden:\n{exc}", exc=exc),
            )
        finally:
            if self.panel is not None:
                self.panel.show()
        self._status("Bereit")

    def on_contour(self) -> None:
        """Aeussere Kante der VectorCraft-Kontur wird zur einzigen Schnittlinie.

        Text wird zuerst in Pfade gewandelt. Ein Strich, der den Buchstaben
        breiter macht, wird durch seine aeusserste Kante ersetzt. Das Loch
        im Buchstaben bleibt. Ohne Strich bleibt die Glyphe samt Loch. Das
        Schneidefenster oeffnet sich hier nicht.
        """
        if not self.ensure_control_channel():
            self._status("Steuerkanal nicht aktiv")
            return
        self._status("Kontur ...")
        try:
            selection = self.vc.export_selection()
        except VcControlError as exc:
            self._status("Fehler")
            popup.warning(
                self.panel,
                "Keine Auswahl",
                i18n.trf("Die Auswahl konnte nicht geholt werden.\n\n{exc}", exc=exc),
            )
            return

        lower = selection.data.lower()
        has_text = b"<text" in lower
        has_path = b"<path" in lower or b"<polygon" in lower or b"<polyline" in lower
        if selection.count == 0 and not has_text and not has_path:
            self._status("Nichts ausgewaehlt")
            popup.warning(
                self.panel,
                "Kontur",
                "Bitte zuerst das Motiv in VectorCraft auswählen.\n\nOhne Auswahl wird nichts umgewandelt.",
            )
            return

        align, fill = self._selection_paint()
        outward = _outward_stroke_pt(selection.data, align)
        steps = 0
        try:
            if has_text:
                self.vc.execute("type.createOutlines")
                steps += 1
            if outward > 0.2:
                steps += self._keep_outer_edge(outward, fill)
            elif not has_text:
                self._status("Kein Strich auf der Auswahl")
                popup.information(
                    self.panel,
                    "Kontur",
                    "Die Auswahl hat keinen Strich, der sie größer macht.\n\n"
                    "In VectorCraft einen Strich auf das Motiv legen und dann noch einmal Kontur klicken. "
                    "Übernommen wird nur die äußerste Kante.",
                )
                return
        except VcControlError as exc:
            self._undo(steps)
            self._status("Kontur fehlgeschlagen")
            popup.critical(
                self.panel,
                "Kontur",
                i18n.trf(
                    "Die äußerste Kante konnte nicht übernommen werden.\n\n{exc}\n\n"
                    "Ist in VectorCraft etwas ausgewählt?",
                    exc=exc,
                ),
            )
            return

        if outward > 0.2:
            self._status("Äußerste Kante übernommen – jetzt Plot klicken")
        else:
            self._status("Text in Kontur umgewandelt – jetzt Plot klicken")

    def _selection_paint(self) -> tuple[str, str]:
        """Strich-Ausrichtung und eine sichtbare Fuellfarbe der Auswahl."""
        align = "center"
        fill = "#111111"
        for pid in self.vc.selection_ids():
            node = self.vc.execute("document.node", {"id": pid, "summary": True}) or {}
            if not isinstance(node, dict):
                continue
            opts = node.get("strokeOptions") or {}
            if isinstance(opts, dict) and opts.get("align"):
                align = str(opts["align"])
            color = node.get("fill")
            if isinstance(color, str) and color.lower() not in ("", "none"):
                fill = color
        return align, fill

    def _keep_outer_edge(self, outward_pt: float, fill: str) -> int:
        """Ersetzt die Auswahl durch die aeusserste Kante des Strichs.

        Der versetzte Pfad behaelt das Loch im Buchstaben. Weg fallen nur die
        alten Pfade und der Strich. Gibt die Undo-Schritte zurueck.
        """
        steps = 0
        originals = self.vc.selection_ids()
        created = self.vc.execute(
            "object.path.offsetPath",
            {"offset": outward_pt, "joins": "round"},
        )
        steps += 1
        new_ids = [int(i) for i in ((created or {}).get("ids") or [])]
        if not new_ids:
            raise VcControlError("Aus dem Strich wurde keine Aussenkante.")

        remove = [i for i in originals if i not in new_ids]
        if remove:
            self.vc.execute("edit.clear", {"ids": remove})
            steps += 1
        self.vc.execute("select.set", {"ids": new_ids})
        self.vc.execute("paint.setFill", {"color": fill, "ids": new_ids, "keepModel": True})
        steps += 1
        self.vc.execute("paint.setStroke", {"none": True, "ids": new_ids})
        steps += 1
        return steps

    def _undo(self, steps: int) -> None:
        for _ in range(max(0, steps)):
            try:
                self.vc.execute("edit.undo")
            except VcControlError:
                break

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
        self._status("Plotter: {name}", name=self.profile_name)

    def on_test_connection(self) -> None:
        from .transport import build_transport

        # Steuerkanal
        vc_ok = self.vc.ping()
        transport = build_transport(self.profile["transport"])
        tr_ok, tr_msg = transport.test()

        lines = [
            i18n.trf(
                "VectorCraft-Steuerkanal ({host}:{port}): {state}",
                host=self.vc.host,
                port=self.vc.port,
                state=i18n.tr("OK" if vc_ok else "nicht erreichbar"),
            ),
            i18n.trf(
                "{name} ({where}): {state}",
                name=self.profile_name,
                where=transport.describe(),
                state=i18n.tr("OK" if tr_ok else "Fehler"),
            ),
            tr_msg,
        ]
        popup.information(self.panel, "Verbindungstest", "\n".join(lines))
        self._status("Test abgeschlossen")

    def show_info(self) -> None:
        from . import __version__

        popup.information(
            self.panel,
            "Plot Cut",
            i18n.trf(
                "Plot Cut v{version}\n\n"
                "Schneide-Panel für VectorCraft. Es steuert Plotter wie Mimaki und Vevor, "
                "direkt per USB oder über den Loki-PrintServer.\n\n"
                "FineCut ist eine Marke von Mimaki; dieses Projekt ist unabhängig.",
                version=__version__,
            ),
        )
