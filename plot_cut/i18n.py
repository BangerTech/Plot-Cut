"""Oberflächensprache. Deutsch ist der Quelltext, Englisch die Übersetzung.

``tr`` übersetzt eine feste Zeichenkette. ``trf`` füllt danach ``{platzhalter}``.
Widgets mit ``bind`` lassen sich später mit ``retranslate`` umschalten.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable

_LANG = "de"
_LISTENERS: list[Callable[[], None]] = []

EN: dict[str, str] = {
    # Panel und Tray
    "Plotter": "Plotter",
    "Aktiven Plotter wählen": "Choose the active plotter",
    "Info / Verbindung": "Info / connection",
    "Log": "Log",
    "Gesendete Aufträge anzeigen": "Show jobs that were sent",
    "Protokoll": "Log",
    "Einträge älter als 7 Tage werden gelöscht. Unten steht der Befehlsstrom, der rausgegangen ist.": (
        "Entries older than 7 days are deleted. Below is the command stream that went out."
    ),
    "Aktualisieren": "Refresh",
    "Schliessen": "Close",
    "Noch kein Eintrag.": "No entries yet.",
    "Panel schliessen": "Close the panel",
    "Auswahl schneiden (Plot)": "Cut the selection (Plot)",
    "Plotter/User Setup": "Plotter / user setup",
    "Verbindung testen": "Test connection",
    "Kontur": "Contour",
    "Äußerste Kante der Kontur als Schnittlinie": "Use the outermost edge of the contour as the cut line",
    "Entgittern": "Weed",
    "Entgitterlinien (folgt)": "Weed lines (later)",
    "Cut-Ebene": "Cut layer",
    "Auf Cut-Ebene verschieben (folgt)": "Move to the cut layer (later)",
    "Marken": "Marks",
    "Passermarken im Plot-Fenster": "Registration marks in the Plot window",
    "Linien bearbeiten (folgt)": "Edit lines (later)",
    "Ausgabe an RasterLink (folgt)": "Send to RasterLink (later)",
    "Bereit": "Ready",
    "Panel anzeigen": "Show panel",
    "Plot ...": "Plot ...",
    "Setup ...": "Setup ...",
    "Beenden": "Quit",
    "Plotter: {name}": "Plotter: {name}",
    # Status
    "Steuerkanal nicht aktiv": "Control channel is not running",
    "Hole Auswahl ...": "Reading the selection ...",
    "Fehler": "Error",
    "Hinweis: evtl. nichts ausgewaehlt": "Note: maybe nothing is selected",
    "Fehler beim Lesen": "Could not read the selection",
    "{n} Pfade geladen": "{n} paths loaded",
    "Keine Pfade": "No paths",
    "Starte VectorCraft ...": "Starting VectorCraft ...",
    "Steuerkanal aktiv": "Control channel is running",
    "Steuerkanal kam nicht hoch": "Control channel did not start",
    "Kontur ...": "Contour ...",
    "Nichts ausgewaehlt": "Nothing selected",
    "Kein Strich auf der Auswahl": "No stroke on the selection",
    "Kontur fehlgeschlagen": "Contour failed",
    "Äußerste Kante übernommen – jetzt Plot klicken": "Outermost edge applied — click Plot",
    "Text in Kontur umgewandelt – jetzt Plot klicken": "Text converted to a contour — click Plot",
    "Test abgeschlossen": "Test finished",
    # Hinweise
    "Steuerkanal nicht aktiv": "Control channel is not running",
    "VectorCraft wurde nicht gefunden. Bitte einmal im Setup den Pfad zu vectorcraft.exe angeben.\n\nDer Steuerkanal (Port {port}) ist nötig, damit die Auswahl gelesen werden kann.": (
        "VectorCraft was not found. Set the path to vectorcraft.exe once in Setup.\n\n"
        "The control channel (port {port}) is required to read the selection."
    ),
    "VectorCraft neu starten?": "Restart VectorCraft?",
    "Der VectorCraft-Steuerkanal ist nicht aktiv.\n\nDamit das Panel die Auswahl holen kann, muss VectorCraft mit aktivem Steuerkanal laufen.\n\nJetzt VectorCraft mit Steuerkanal starten?\n(Eine offene Zeichnung vorher in VectorCraft sichern.)": (
        "The VectorCraft control channel is not running.\n\n"
        "Plot Cut can read the selection only while VectorCraft is running with the control channel.\n\n"
        "Start VectorCraft with the control channel now?\n"
        "(Save an open drawing in VectorCraft first.)"
    ),
    "Start fehlgeschlagen": "Could not start",
    "VectorCraft ({exe}) ließ sich nicht starten.": "VectorCraft ({exe}) could not be started.",
    "Keine Auswahl": "No selection",
    "Die Auswahl konnte nicht geholt werden.\n\n{exc}\n\nLäuft VectorCraft mit '--control {port}' und ist etwas ausgewählt?": (
        "The selection could not be read.\n\n{exc}\n\n"
        "Is VectorCraft running with '--control {port}', and is something selected?"
    ),
    "Die Auswahl konnte nicht geholt werden.\n\n{exc}": "The selection could not be read.\n\n{exc}",
    "Importfehler": "Import error",
    "Text statt Kontur": "Text instead of a contour",
    "Die Auswahl ist Text, zum Beispiel ein Buchstabe.\n\nKontur wandelt ihn in eine Schnittlinie um, so wie FineCut. Danach kann er geschnitten werden.": (
        "The selection is text, for example a letter.\n\n"
        "Contour turns it into a cut line, the way FineCut does. It can then be cut."
    ),
    "Keine Schneidepfade": "No cut paths",
    "In der Auswahl wurden keine Linien/Pfade gefunden.": "No lines or paths were found in the selection.",
    "Plot": "Plot",
    "Das Plot-Fenster konnte nicht geoeffnet werden:\n{exc}": "The plot window could not be opened:\n{exc}",
    "Bitte zuerst das Motiv in VectorCraft auswählen.\n\nOhne Auswahl wird nichts umgewandelt.": (
        "Select the artwork in VectorCraft first.\n\nNothing is converted without a selection."
    ),
    "Die Auswahl hat keinen Strich, der sie größer macht.\n\nIn VectorCraft einen Strich auf das Motiv legen und dann noch einmal Kontur klicken. Übernommen wird nur die äußerste Kante.": (
        "The selection has no stroke that makes it larger.\n\n"
        "Add a stroke in VectorCraft, then click Contour again. Only the outermost edge is kept."
    ),
    "Die äußerste Kante konnte nicht übernommen werden.\n\n{exc}\n\nIst in VectorCraft etwas ausgewählt?": (
        "The outermost edge could not be applied.\n\n{exc}\n\nIs something selected in VectorCraft?"
    ),
    "Verbindungstest": "Connection test",
    "VectorCraft-Steuerkanal ({host}:{port}): {state}": "VectorCraft control channel ({host}:{port}): {state}",
    "nicht erreichbar": "not reachable",
    "OK": "OK",
    "{name} ({where}): {state}": "{name} ({where}): {state}",
    "Plot Cut v{version}\n\nSchneide-Panel für VectorCraft. Es steuert Plotter wie Mimaki und Vevor, direkt per USB oder über den Loki-PrintServer.\n\nFineCut ist eine Marke von Mimaki; dieses Projekt ist unabhängig.": (
        "Plot Cut v{version}\n\n"
        "A cutting panel for VectorCraft. It drives plotters such as Mimaki and Vevor, "
        "over USB on this PC or through Loki-PrintServer.\n\n"
        "FineCut is a trademark of Mimaki; this project is independent."
    ),
    "Ja": "Yes",
    "Nein": "No",
    # Setup
    "Plotter / User Setup": "Plotter / User Setup",
    "Oberfläche": "Language",
    "Deutsch oder English. Das Panel wechselt sofort, dieses Fenster ebenfalls.": (
        "German or English. The panel switches at once, and so does this window."
    ),
    "Speichern": "Save",
    "Abbrechen": "Cancel",
    "VectorCraft (Steuerkanal)": "VectorCraft (control channel)",
    "automatisch gesucht, falls leer": "found automatically if empty",
    "Steuerkanal-Port": "Control-channel port",
    "Plotter-Profil": "Plotter profile",
    "Neu ...": "New ...",
    "Umbenennen ...": "Rename ...",
    "Loeschen": "Delete",
    "Modell": "Model",
    "Befehlssprache": "Command language",
    "MGL-IIc (Mimaki)": "MGL-IIc (Mimaki)",
    "HP-GL (z. B. Vevor)": "HP-GL (for example Vevor)",
    "DMPL": "DMPL",
    "Folienbreite (mm)": "Sheet width (mm)",
    "Folienlänge (mm)": "Sheet length (mm)",
    "Auflösung": "Resolution",
    "Kurvenauflösung (mm)": "Curve resolution (mm)",
    "Verbindung": "Connection",
    "Art": "Type",
    "Loki-Server (USB-Bridge)": "Loki server (USB bridge)",
    "TCP roh (socat / Port 9100)": "Raw TCP (socat / port 9100)",
    "COM-Port": "COM port",
    "Datei (.plt, zum Testen)": "File (.plt, for testing)",
    "Mimaki USB (lokal, wie FineCut)": "Mimaki USB (local, like FineCut)",
    "Loki-Server (IP)": "Loki server (IP)",
    "Port": "Port",
    "Geraete laden": "Load devices",
    "Geraet": "Device",
    "Host": "Host",
    "z. B. COM5 oder auto": "e.g. COM5 or auto",
    "auto = CH340-Plotter (z. B. Vevor) selbst finden, direkt am PC oder per Loki-Client": (
        "auto finds a CH340 plotter (such as a Vevor), plugged into this PC or attached by the Loki client"
    ),
    "Baudrate": "Baud rate",
    "Dateipfad": "File path",
    "Schreibt wie FineCut an den Mimaki-USB-Treiber. Der Cutter kann direkt an diesem PC stecken oder vom Loki-Client per USB/IP angehängt sein. Leer lassen sucht den Treiber selbst.": (
        "Writes to the Mimaki USB driver the way FineCut does. The cutter can be plugged into this PC, "
        "or attached by the Loki client over USB/IP. Leave the path empty to find the driver."
    ),
    "leer = automatisch finden": "empty = find automatically",
    "Geraetepfad": "Device path",
    "Standard-Schneidbedingung": "Default cut condition",
    "Geschwindigkeit (cm/s)": "Speed (cm/s)",
    "Druck (g)": "Pressure (g)",
    "Klingenoffset (mm)": "Blade offset (mm)",
    "Favoriten (Schneidbedingungen)": "Favorites (cut conditions)",
    "Laden": "Load",
    "Speichern als ...": "Save as ...",
    "Neuer Plotter": "New plotter",
    "Name des Plotters:": "Plotter name:",
    "'{name}' gibt es schon.": "'{name}' already exists.",
    "Umbenennen": "Rename",
    "Neuer Name:": "New name:",
    "'{name}' ist schon vergeben.": "'{name}' is already in use.",
    "Mindestens ein Plotter muss bleiben.": "At least one plotter has to stay.",
    "Plotter '{name}' löschen?": "Delete plotter '{name}'?",
    "vectorcraft.exe wählen": "Choose vectorcraft.exe",
    "Programme (*.exe)": "Programs (*.exe)",
    " - belegt": " — in use",
    "Loki": "Loki",
    "Loki meldet keine Plotter.": "Loki reports no plotters.",
    "Favorit speichern": "Save favorite",
    "Name:": "Name:",
    # Plot
    "Plot — {name}": "Plot — {name}",
    "Vorschau": "Preview",
    "Schneidelinie": "Cut line",
    "Initialisieren": "Initialize",
    "Alle Einstellungen dieses Fensters zurücksetzen": "Reset every setting in this window",
    "Blattgröße einlesen": "Read sheet size",
    "Folienbreite und -länge vom Plotter lesen, sonst aus dem Profil": (
        "Read sheet width and length from the plotter, otherwise from the profile"
    ),
    "Vom Plotter gelesen: {w} × {h} mm.": "Read from the plotter: {w} × {h} mm.",
    "Keine Antwort auf OH;. Werte aus dem Profil.": "No reply to OH;. Using the profile values.",
    "Schneiden...": "Cut...",
    "Weiter zum Ausplotten": "Continue to output",
    "Fenster schließen": "Close the window",
    "Blattgröße": "Sheet size",
    "Offset": "Offset",
    "Größe": "Size",
    "Skalierung(%)": "Scale (%)",
    "Kopieren": "Copy",
    "Kopierabstand": "Copy spacing",
    "Rahmen": "Frame",
    "Rechteck um das Motiv mitschneiden. Das Motiv rückt um den Abstand vom Ursprung weg.": (
        "Cut a rectangle around the artwork. The artwork moves away from the origin by that margin."
    ),
    "Seitenverhältnis gekoppelt (Verzerren aus)": "Aspect ratio is linked (Distort is off)",
    "Drehen": "Rotate",
    "Um 90 Grad drehen": "Rotate by 90 degrees",
    "Bewegen": "Move",
    "Motiv auf der Folie platzieren": "Place the artwork on the sheet",
    "Anpassen": "Fit",
    "Motiv proportional auf die Folie skalieren": "Scale the artwork to the sheet, keeping proportions",
    "Original Layout": "Original layout",
    "Drehung, Größe, Spiegeln und Lage zurücksetzen": "Reset rotation, size, mirror and position",
    "Spiegeln": "Mirror",
    "Spiegeln H": "Mirror H",
    "Spiegeln V": "Mirror V",
    "WYSIWYG": "WYSIWYG",
    "Lage auf der Zeichenfläche behalten. Aus = Motiv an den Plotter-Ursprung schieben.": (
        "Keep the artwork where it sits on the page. Off = move it to the plotter origin."
    ),
    "Kurvenauflösung": "Curve resolution",
    "Maximale Abweichung, bevor eine Kurve zur Geraden wird. Gilt beim nächsten Laden.": (
        "Maximum deviation before a curve becomes a straight line. Applies the next time a design is loaded."
    ),
    "Bahnen": "Tiles",
    "Motiv in Foliengrösse teilen, wenn es grösser als die Folie ist.": (
        "Split the artwork into sheet-sized tiles when it is larger than the sheet."
    ),
    "Überlappung": "Overlap",
    "Bahn {x} / {y}": "Tile {x} / {y}",
    "Passermarken mitschneiden": "Cut registration marks",
    "Innen": "Inside",
    "Aus = aussen um das Motiv, an = innen am Rand.": "Off = outside the artwork, on = inset from the edge.",
    "Linienbreite": "Line width",
    "Runde Füllung": "Round fill",
    "Zusätzliche Marke": "Extra mark",
    "Mehrfachschnitt": "Multi-cut",
    "Zusätzliche Schnitte über denselben Pfad": "Extra passes over the same path",
    "Nach jeder Farbe anhalten": "Pause after each color",
    "Nach dem Schnitt": "After the cut",
    "Zum Ursprung": "Return to origin",
    "Folie vorschieben": "Advance the sheet",
    "Stehen bleiben": "Do nothing",
    "Nächste Farbe": "Next color",
    "Die nächste Farbe ist bereit. Folie wechseln oder Blatt prüfen, dann Ja zum Weiterschneiden.": (
        "The next color is ready. Change the sheet or check the material, then Yes to keep cutting."
    ),
    "TCP-Lesen an {host}:{port} fehlgeschlagen: {exc}": "TCP read from {host}:{port} failed: {exc}",
    "Serielles Lesen an {port} fehlgeschlagen: {exc}": "Serial read from {port} failed: {exc}",
    "Mimaki-Abfrage fehlgeschlagen (Windows-Fehler {err}).": "Mimaki query failed (Windows error {err}).",
    "Verzerren": "Distort",
    "Breite und Höhe unabhängig ändern": "Change width and height independently",
    "Nullpunkt fest": "Fix origin",
    "Motiv bleibt am Plotter-Ursprung, Bewegen und Offset sind aus": (
        "The artwork stays on the plotter origin. Move and offset are off."
    ),
    "Justiermarke Mitte": "Register mark, center",
    "Justiermarke Ecke": "Register mark, corner",
    "Justiermarken folgen in einer späteren Version": "Register marks will come in a later version",
    "Einheit:": "Unit:",
    "Layout": "Layout",
    "Kacheln: große Motive in Bahnen mit Überlappung aufteilen. Kommt in einer späteren Version.": (
        "Tiles: split a large design into strips with overlap. Coming in a later version."
    ),
    "Kacheln Abstand": "Tile spacing",
    "Passermarken (Konturschnitt nach Druck) kommen in einer späteren Version.": (
        "Registration marks (contour cut after printing) will come in a later version."
    ),
    "Passermarken": "Registration marks",
    "Farbe": "Color",
    "Ebenen kommen, sobald VectorCraft sie mit der Auswahl liefert. Bis dahin über die Farbe wählen.": (
        "Layers will appear once VectorCraft sends them with the selection. Until then, choose by color."
    ),
    "Ebene": "Layer",
    "Breiter als die Folie": "Wider than the sheet",
    "Ausplotten": "Output",
    "Das Ausplotten-Fenster konnte nicht geoeffnet werden:\n{exc}": "The output window could not be opened:\n{exc}",
    "Position auf der Folie": "Position on the sheet",
    # Ausplotten
    "Ausplotten — {name}": "Output — {name}",
    "Schneiden": "Cut",
    "Vorschau...": "Preview...",
    "Speichern als Datei...": "Save as file...",
    "Save Preset Setting": "Save preset setting",
    "Plot-Einstellung": "Plot setting",
    "Plotter-Einstellung": "Plotter setting",
    "Auswahl-Einstellung": "Selection setting",
    "Benutzerdefiniert": "Custom",
    "Bearbeiten...": "Edit...",
    "Presets im Setup verwalten": "Manage presets in Setup",
    "Werkzeug": "Tool",
    "Geschwindigkeit": "Speed",
    "Andruck": "Pressure",
    "Schneidbedingung je Farbe": "Cut condition per color",
    "Bedingung": "Condition",
    "Optionen": "Options",
    "Sortieren": "Sort",
    "Alle": "All",
    "Jede Farbe": "Each color",
    "Innen vor Außen": "Inside before outside",
    "Kopf in Parkposition": "Park the head",
    "Nach dem Schnitt fährt der Kopf hinter das Motiv, damit die Folie abgeschnitten werden kann.": (
        "After the cut, the head moves past the artwork so the sheet can be cut off."
    ),
    "Abstand hinter dem Motiv": "Gap past the artwork",
    "Abstand": "Gap",
    "Overcut": "Overcut",
    "(keine Presets gespeichert)": "(no presets saved)",
    "Wie Plot-Einstellung": "Same as plot setting",
    "Preset: {name}": "Preset: {name}",
    "Nicht schneiden": "Do not cut",
    "Pfade: {n}    Schnittlänge: {cm} cm": "Paths: {n}    Cut length: {cm} cm",
    "Name für die aktuelle Schneidbedingung:": "Name for the current cut condition:",
    "Preset": "Preset",
    'Preset "{name}" gespeichert.': 'Preset "{name}" saved.',
    "Senden fehlgeschlagen": "Send failed",
    "Gesendet an {where} ({n} Bytes).": "Sent to {where} ({n} bytes).",
    "Plotdatei speichern": "Save plot file",
    "Plot (*.plt)": "Plot (*.plt)",
    "Gespeichert": "Saved",
    "{n} Bytes nach {path}.": "{n} bytes written to {path}.",
    "Richtungspfeile": "Direction arrows",
    "Reihenfolge-Nummern": "Order numbers",
    "Leerfahrten (gelb)": "Travel moves (yellow)",
    "schwarz = gegen Uhrzeigersinn\nrot = im Uhrzeigersinn\ngelb = Leerfahrt": (
        "black = counterclockwise\nred = clockwise\nyellow = travel"
    ),
    "Simulation": "Simulation",
    "Schnittlänge: {cm} cm": "Cut length: {cm} cm",
    "Schließen": "Close",
    "Einpassen": "Fit",
    "Auf das Objekt zoomen (auch Doppelklick in die Vorschau)": "Zoom to the artwork (or double-click the preview)",
    "Ganze Folie": "Whole sheet",
    "Gesamte Folienbreite anzeigen": "Show the full sheet width",
    # Transport
    "Kein Loki-Gerät gewählt (Setup -> Verbindung -> Gerät).": "No Loki device selected (Setup -> Connection -> Device).",
    "Loki erreichbar, aber kein Gerät gewählt. Verfügbar: {names}": (
        "Loki is reachable, but no device is selected. Available: {names}"
    ),
    "Loki kennt das Gerät '{device}' nicht.": "Loki does not know the device '{device}'.",
    "'{name}' ist gerade belegt{who}.": "'{name}' is busy{who}.",
    " (angehängt an {where})": " (attached to {where})",
    "'{name}' ist bereit ({kind}).": "'{name}' is ready ({kind}).",
    "Gerät": "Device",
    "Loki: {detail}": "Loki: {detail}",
    "Loki unter {host}:{port} nicht erreichbar: {exc}": "Loki at {host}:{port} is not reachable: {exc}",
    "Gerät oder Plot-Cut-API nicht gefunden (Loki aktualisiert?)": (
        "Device or Plot Cut API not found (is Loki up to date?)"
    ),
    "Gerät ist belegt (z. B. per USB/IP an einen PC angehängt)": (
        "Device is busy (for example attached to a PC over USB/IP)"
    ),
    "Gerät ist nicht angeschlossen": "Device is not connected",
    "Der Mimaki hängt bei Loki im USB/IP-Modus für FineCut. Plot Cut schickt den Auftrag an die USB-Bridge von Loki, und die sieht das Gerät in diesem Modus nicht.\n\nEs wurde nichts an den Plotter geschrieben.\n\nAbhilfe: Im Setup unter Verbindung die Art \"Mimaki USB (lokal, wie FineCut)\" wählen. Dann schreibt Plot Cut wie FineCut an den Cutter, auch wenn er per USB/IP oder direkt am PC hängt.": (
        "The Mimaki is attached in Loki's USB/IP mode for FineCut. Plot Cut sent the job to Loki's USB bridge, "
        "which cannot see the device in that mode.\n\nNothing was written to the plotter.\n\n"
        "In Setup, under Connection, choose \"Mimaki USB (local, like FineCut)\". "
        "Plot Cut then writes like FineCut, whether the cutter is on USB/IP or plugged into this PC."
    ),
    "TCP-Senden an {host}:{port} fehlgeschlagen: {exc}": "TCP send to {host}:{port} failed: {exc}",
    "Verbindung zu {host}:{port} steht.": "Connected to {host}:{port}.",
    "Keine Verbindung zu {host}:{port}: {exc}": "No connection to {host}:{port}: {exc}",
    "Kein USB-Seriell-Plotter (CH340) gefunden. Steckt der Plotter direkt am PC, oder ist er im Loki-Client angehängt?": (
        "No USB-serial plotter (CH340) found. Is the plotter plugged into this PC, or attached in the Loki client?"
    ),
    "Serielles Senden an {port} fehlgeschlagen: {exc}": "Serial send to {port} failed: {exc}",
    "Port {port} geöffnet.": "Port {port} is open.",
    "Port {port} nicht verfügbar: {exc}": "Port {port} is not available: {exc}",
    "COM {port} @ {baud}": "COM {port} @ {baud}",
    "Kein Mimaki-USB-Gerät gefunden. Steckt der Cutter direkt an diesem PC, oder hängt ihn der Loki-Client per USB/IP an, und ist der Mimaki-Treiber installiert?": (
        "No Mimaki USB device found. Is the cutter plugged into this PC, or attached by the Loki client over USB/IP, "
        "and is the Mimaki driver installed?"
    ),
    "Mimaki-USB-Gerät lässt sich nicht öffnen (Windows-Fehler {err}). Ist der Cutter eingeschaltet und angeschlossen?": (
        "The Mimaki USB device cannot be opened (Windows error {err}). Is the cutter switched on and connected?"
    ),
    "Schreiben an den Mimaki abgebrochen nach {done} von {total} Bytes (Windows-Fehler {err}).": (
        "Writing to the Mimaki stopped after {done} of {total} bytes (Windows error {err})."
    ),
    "Mimaki-USB-Gerät bereit:\n{path}": "Mimaki USB device is ready:\n{path}",
    "Mimaki USB (lokal)": "Mimaki USB (local)",
    "Datei {path} konnte nicht geschrieben werden: {exc}": "Could not write file {path}: {exc}",
    "Schreibe nach {path}.": "Will write to {path}.",
    "Ordner existiert nicht: {parent}": "Folder does not exist: {parent}",
    "Datei {path}": "File {path}",
    "pyserial ist nicht installiert. Bitte 'pip install pyserial' ausführen.": (
        "pyserial is not installed. Run 'pip install pyserial'."
    ),
    "Unbekannter Transport: {kind}": "Unknown transport: {kind}",
    "TCP {host}:{port}": "TCP {host}:{port}",
    "Loki {host}:{port} / {device}": "Loki {host}:{port} / {device}",
}


def language() -> str:
    return _LANG


def set_language(lang: str) -> None:
    """``de`` oder ``en``. Andere Werte fallen auf Deutsch zurück."""
    global _LANG
    _LANG = "en" if lang == "en" else "de"
    for listener in list(_LISTENERS):
        listener()


def tr(source: str) -> str:
    if _LANG != "en" or not source:
        return source
    return EN.get(source, source)


def trf(source: str, **values: object) -> str:
    return tr(source).format(**values)


def bind(widget, **roles: str) -> None:
    """Merkt sich die deutschen Quelltexte und zeigt die aktuelle Sprache."""
    widget._i18n = roles  # noqa: SLF001
    _apply(widget)


def watch(root) -> None:
    """Übersetzt ``root`` neu, sobald die Sprache wechselt."""
    ref = weakref.ref(root)

    def refresh() -> None:
        widget = ref()
        if widget is None:
            if refresh in _LISTENERS:
                _LISTENERS.remove(refresh)
            return
        retranslate(widget)

    _LISTENERS.append(refresh)


def retranslate(root) -> None:
    from PySide6.QtCore import QObject

    _apply(root)
    for obj in root.findChildren(QObject):
        _apply(obj)
        items = getattr(obj, "_i18n_items", None)
        if items:
            _fill_items(obj)


def bind_items(combo, items: list[tuple[str, object]]) -> None:
    """Feste Einträge ``(quelltext, data)``. Die Auswahl bleibt beim Umschalten."""
    combo._i18n_items = items  # noqa: SLF001
    _fill_items(combo)


def _fill_items(combo) -> None:
    current = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    for source, data in combo._i18n_items:
        combo.addItem(tr(source), data)
    index = combo.findData(current)
    if index >= 0:
        combo.setCurrentIndex(index)
    combo.blockSignals(False)


def _apply(widget) -> None:
    status = getattr(widget, "_i18n_status", None)
    if isinstance(status, tuple) and len(status) == 2:
        source, fmt = status
        widget.setText(trf(source, **fmt))
        return
    roles = getattr(widget, "_i18n", None)
    if not isinstance(roles, dict):
        return
    if "text" in roles and hasattr(widget, "setText"):
        widget.setText(tr(roles["text"]))
    if "title" in roles and hasattr(widget, "setTitle"):
        widget.setTitle(tr(roles["title"]))
    if "window" in roles and hasattr(widget, "setWindowTitle"):
        widget.setWindowTitle(tr(roles["window"]))
    if "tip" in roles and hasattr(widget, "setToolTip"):
        widget.setToolTip(tr(roles["tip"]))
    if "placeholder" in roles and hasattr(widget, "setPlaceholderText"):
        widget.setPlaceholderText(tr(roles["placeholder"]))


def lab(source: str, *, wrap: bool = False):
    from PySide6.QtWidgets import QLabel

    widget = QLabel()
    if wrap:
        widget.setWordWrap(True)
    bind(widget, text=source)
    return widget
