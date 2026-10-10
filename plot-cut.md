# Plot Cut

Ein schwebendes Schneideplotter-Panel fuer VectorCraft im Stil von Mimaki FineCut. Es ahmt
den FineCut-Ablauf aus Adobe Illustrator nach: Auswahl aus VectorCraft holen, Plot- und
Plot-Out-Fenster mit Vorschau und Simulation anzeigen und die Schneidedaten (MGL-IIc oder
HP-GL) ueber den Loki-PrintServer an einen von mehreren Plottern senden (z. B. Mimaki
CG-60SR und Vevor). Frueherer Name: "Mimaki Cut".

## Warum ein externes Panel?

Die WebAssembly-Plug-in-Schnittstelle von VectorCraft (ABI v1) laesst keine Panel-Plug-ins
und keinen Netzwerkzugriff zu (siehe `docs/plugins.md`, Abschnitt "Not in v1"). Ein Plug-in
kann also weder ein Dock-Panel bauen noch an den Plotter senden. Deshalb ist Plot Cut ein
eigenstaendiges, immer im Vordergrund liegendes Fenster, das sich ueber den **Steuerkanal**
von VectorCraft (`vectorcraft --control 7979`) mit dem Programm unterhaelt.

## Architektur

```
VectorCraft (--control 7979)
   | JSON (eine Zeile pro Request) ueber TCP 127.0.0.1:7979
   v
vc_control.py  ---- Auswahl als SVG/DXF, Dateipfad, Ebenen
   v
geometry.py    ---- SVG/DXF -> Polylinien (mm), Transformationen, Sortierung, Overcut
   v
mgl.py         ---- MGL-IIc / HP-GL erzeugen (Sprache je Plotter-Profil)
   v
transport.py   ---- Loki-HTTP | TCP (socat am Pi) | COM-Port | Datei (.plt)
   v
Loki-PrintServer -> Plotter (Mimaki CG-60SR, Vevor, ...)
```

Die GUI (PySide6) sitzt obenauf:

- `ui/panel.py`            Werkzeugfenster im FineCut-Look, Profilauswahl, immer im Vordergrund
- `ui/plot_dialog.py`      [Plot]: Folienvorschau, Drehen, Spiegeln, Kopien
- `ui/plot_out_dialog.py`  [Plot Out]: Schneidbedingungen, Vorschau mit Farbcodes, Simulation, Senden
- `ui/setup_dialog.py`     Setup: VectorCraft, Plotter-Profile, Verbindung, Bedingungen, Favoriten
- `ui/preview.py`          gemeinsame Vorschau (Folie, Raster, Masse, Zoom/Pan)

## Datenfluss / Koordinaten

- VectorCraft exportiert SVG mit **einheitenlosem** `width`/`height` in **Punkten** (A4 =
  595.276 x 841.89). svgelements wuerde das als 96-dpi-px lesen (30 mm -> 22,5 mm). Darum
  rechnet `geometry._svg_scale` einheitenlose Werte als pt (25,4/72 mm) und Werte mit
  Einheit als CSS-px (25,4/96 mm). Regressionstest: `test_vectorcraft_svg_is_in_points`.
- Intern wird alles in Millimetern gefuehrt, y nach oben, Ursprung = Plotter-Nullpunkt.
- MGL-IIc-Einheit: 1 Schritt = 0,025 mm (mm * 40 = Schritte).
- Bezierkurven werden mit einer Toleranz von 0,05 mm zu Polylinien abgeflacht.

## Vorschau

- FineCut/Mimaki (`mgl2`): Ursprung **rechts unten**. Maschinen-X waechst von
  dort nach links in die Folie, Y nach oben. Die Form bleibt seitenrichtig
  (rechte Kante des Motivs am Ursprung). Links neben der Folienbreite ist grau.
  Kein Karopapier, Millimeter-Lineal unten, 0 an der Ursprungsmarke.
- HP-GL/Vevor: Ursprung links unten, X nach rechts.
- FineCuts "Rahmen" ist eine Extra-Verschiebung und wird nicht nachgebaut.
  Ohne Rahmen liegt die Ecke direkt auf (0, 0).
- Plot-Dialog: Tabs **Vorschau** (gefuellt) und **Schneidelinie** (nur Kontur).
  Rechte Leiste wie FineCut:
  - Runde Knoepfe: Initialisieren (alles zuruecksetzen), Blattgröße einlesen
    (aus dem Profil, noch keine Geraeteabfrage), Schneiden... (-> Ausplotten), Beenden.
  - Tabelle mit ↔/↕: Blattgröße, Offset, Größe, Skalierung(%) (gekoppelt "—",
    ausser bei Verzerren), Kopieren X/Y als Raster, Kopierabstand X/Y,
    Rahmen (Haken + Abstand X/Y, wird mitgeschnitten). Darunter Gesamtmass;
    rot, wenn breiter als die Folie.
  - Tabs Layout / Kacheln Abstand / Passermarken. Layout: Drehen (90°),
    Bewegen (9 Positionen auf der Folie), Anpassen (proportional auf die Folie
    skalieren), Original Layout; Spiegeln, Verzerren, Nullpunkt fest. Kacheln,
    Passermarken und Justiermarken sind sichtbar, aber noch ohne Funktion.
  - Tabs Farbe / Ebene: Farbliste mit Haken, abgehakte Farben werden nicht geschnitten.
  Reihenfolge der Platzierung: drehen/spiegeln, skalieren, an Ursprung, Rahmen,
  Kopienraster, dann Bewegen-Position + Offset (nicht bei Nullpunkt fest).
- Ausplotten (frueher "Plot Out") wie FineCut: Plot-Einstellung mit
  Plotter-Einstellung (keine Bedingungsbefehle), Auswahl-Einstellung (Preset aus
  `favorites`) oder Benutzerdefiniert (Werkzeug CT1-3, Geschwindigkeit/Andruck/Offset
  einzeln abwaehlbar = Wert am Plotter lassen). Bedingung je Farbe (Preset oder
  "Nicht schneiden", gespeichert in `conditions_by_color`). Optionen: Sortieren
  (Alle / Jede Farbe, Innen vor Aussen), Overcut, Kopf in Parkposition (Abstand
  hinter dem Motiv). Rechts: Schneiden, Abbrechen, Vorschau... (eigenes Fenster mit
  Richtung, Reihenfolge, Leerfahrten, Simulation), Speichern als Datei..., Save Preset Setting.
- Sortierung: Leerfahrt-Optimierung nur innerhalb einer Verschachtelungstiefe,
  sonst kam der Rahmen vor den Innenteilen. Alle Transformationen behalten `kind`.
- Plot-Dialoge erzwingen dunkle Schrift (`#111`), damit Windows-Dunkelmodus
  keine weissen Buttons ohne Text erzeugt.
- Erstes Einpassen wartet, bis das Fenster eine echte Groesse hat (sonst blieb die
  Vorschau schwarz, Massstab 0).
- Plot Out: schwarz = gegen Uhrzeigersinn, rot = im Uhrzeigersinn, gelb = Leerfahrt.
- Mausrad = Zoom, Ziehen = verschieben, Doppelklick = ganze Folie / einpassen.
- Das Panel wird waehrend Plot/Plot Out versteckt, damit es die Dialoge nicht ueberdeckt.
- Hinweise (Info, Warnung, Fehler) bleiben vor dem immer-oben-Panel und brechen den Text um (`ui/popup.py`).
- Dropdowns (Kopienrichtung, Profile) oeffnen sich ebenfalls vor dem Fenster, mit dunkler Schrift auf weiss.
- Die Kacheln im Panel zentrieren Icon und Beschriftung.
- **Oberfläche** im Setup: `ui.language` ist `de` oder `en`. Deutsch bleibt der
  Quelltext (`plot_cut/i18n.py`), English übersetzt Fenster, Panel, Hinweise und
  Verbindungstexte. Die Befehlssprache des Plotters (MGL-IIc / HP-GL) ist davon
  getrennt. Der Wechsel gilt sofort für das Panel und das offene Setup. Abbrechen
  stellt die vorige Sprache wieder her.
- **Kontur** (FineCut): kein Extra-Fenster und kein Plot-Fenster. VectorCraft
  liefert Text als `<text>` ohne Pfad. Kontur macht daraus `type.createOutlines`.
  Liegt auf dem Motiv ein Strich, der es groesser oder die Linien breiter macht
  (Aussehen-Bedienfeld, Ausrichtung Mitte oder Aussen), ersetzt
  `object.path.offsetPath` die Form durch die aeusserste Kante: halbe sichtbare
  Strichbreite bei Mitte, die ganze bei Aussen (Text-Skalierung aus der
  SVG-Matrix). Das Loch im Buchstaben bleibt im Compound. Geloescht werden nur
  die alten Pfade, der Strich faellt weg. Ohne Strich bleibt die Glyphe samt
  Loch. Ein Strich nur innen aendert die Aussenkante nicht. Plot auf reinem Text
  weist auf Kontur hin. Rueckgaengig mit Undo in VectorCraft.
- Vorschau fuellt Teilpfade eines Pfads mit der Gerade-Ungerade-Regel, damit
  das Loch im P frei bleibt. Der Tab Schneidelinie zeigt alle Schnittlinien.

## Einstellungen (keine Datenbank)

Das Projekt nutzt keine Datenbank. Alle Einstellungen liegen als JSON unter
`%APPDATA%\PlotCut\settings.json` (Code: `plot_cut/settings.py`).

### Schema Version 2 (aktuell)

```json
{
  "version": 2,
  "control": {
    "host": "127.0.0.1",
    "port": 7979,
    "vectorcraft_exe": "",          // leer = automatisch suchen
    "auto_start": true
  },
  "active_profile": "Mimaki CG-60SR",
  "profiles": {
    "Mimaki CG-60SR": {
      "plotter": {
        "model": "CG-60SR",
        "language": "mgl2",         // "mgl2" (MGL-IIc) | "hpgl"
        "sheet_width_mm": 610.0
      },
      "transport": {
        "kind": "mimaki_usb",       // "mimaki_usb" | "loki" | "tcp" | "serial" | "file"
        "usb_path": "",             // nur mimaki_usb, leer = automatisch
        "host": "192.168.1.50",     // Raspberry Pi mit Loki
        "loki_port": 7576,          // Loki-HTTP-API
        "device": "mimaki-cg60sr",  // Loki-Geraete-id
        "port": 7580,               // nur kind=tcp (socat)
        "serial_port": "COM3",      // nur kind=serial; "auto" = CH340 (Vevor) suchen
        "baud": 9600,
        "file_path": "out.plt"      // nur kind=file
      },
      "defaults": {
        "speed": 30,                // cm/s
        "pressure": 100,            // g
        "offset": 0.3,              // mm Klingenoffset
        "overcut_mm": 0.0,
        "sort": true,
        "inner_first": true,
        "send_conditions": true,    // SP/VS/FS/!PT mitsenden (aus condition_source abgeleitet)
        "condition_source": "custom", // "plotter" | "preset" | "custom" (Ausplotten)
        "preset": "",               // Name aus favorites bei "preset"
        "tool": 1,                  // CT1-3 -> SPn
        "use_speed": true,          // false = VS nicht senden
        "use_pressure": true,       // false = FS nicht senden
        "use_offset": true,         // false = !PT nicht senden
        "sort_mode": "all",         // "all" | "color"
        "park": true,               // Kopf nach dem Schnitt hinter das Motiv
        "park_mm": 20.0
      },
      "conditions_by_color": {
        // "#rrggbb": { "preset": "Name", "tool": 1, "speed": 30, "pressure": 100, "offset": 0.3, "enabled": true }
        // "#rrggbb": { "enabled": false }   // Nicht schneiden
      }
    },
    "Vevor": { "...": "gleiche Struktur, language hpgl, 720 mm, 20 cm/s, 80 g, 0.25 mm" }
  },
  "favorites": {
    // "Name": { "tool": 1, "speed": 30, "pressure": 100, "offset": 0.3 }  (= Presets)
  },
  "per_file": {
    // "C:/pfad/zeichnung.vectorcraft": {
    //   "rotate_index": 0, "mirror": false, "distort": false, "fixed_origin": false,
    //   "copies_x": 1, "copies_y": 1, "gap_x": 10, "gap_y": 10,
    //   "offset_x": 0, "offset_y": 0, "anchor": [0, 0],   // Bewegen: Anteil X/Y der Folie
    //   "frame_on": false, "frame_x": 10, "frame_y": 10, "disabled_colors": []
    // }
    // Alte Schluessel copies/copy_axis/copy_gap/frame_mm werden beim Oeffnen uebernommen.
  },
  "ui": {
    "language": "de",             // "de" | "en", Oberflaeche (nicht die Befehlssprache)
    "panel_pos": [0, 0]
  }
}
```

### Migrationen

- **Ordner**: Fehlt `%APPDATA%\PlotCut\settings.json`, wird `%APPDATA%\MimakiCut\settings.json`
  (alter Name) gelesen und beim naechsten Speichern unter `PlotCut` abgelegt.
- **v1 -> v2** (`settings.migrate`): Die frueheren Top-Level-Schluessel `plotter`, `transport`,
  `defaults`, `conditions_by_color` werden zum Profil "Mimaki CG-60SR". Fehlende Standard-
  profile werden nur bei der Migration ergaenzt. Vom Benutzer geloeschte Profile bleiben
  geloescht. Fehlende Schluessel werden mit Standardwerten aufgefuellt.

## Loki-PrintServer (1.4.16)

Loki (https://github.com/BangerTech/Loki-PrintServer) teilt USB-Plotter vom Raspberry Pi.
Plot Cut erzeugt die Befehle selbst; Loki schreibt nur Bytes. Der genaue Server-Auftrag
steht in `LOKI-KI-AUFTRAG.md` — an die echte Loki-Architektur angelehnt, nicht an eine
erfundene tty-Welt.

| Port | Zweck |
|---|---|
| 7575 | USB/IP (FineCut unter Windows, `attach-mode=usbip`) |
| 7576 | FastAPI + Dashboard. Plot Cut: `/api/plotcut/*` (Loki 1.5.0) |
| 7580+ | socat Serial-over-TCP (Vevor CH340 `1a86:7523`) |
| 631 | CUPS / IPP |

| Plotter | USB | Loki-Weg | Plot-Cut-Profil |
|---|---|---|---|
| Mimaki CG-60SR | VID `0x0A50`, Vendor-USB, kein tty | `usb_bridge.py` Raw-USB (Bulk); nicht `usbserial` | `loki` + device `mimaki-cg60sr`, Sprache `mgl2` |
| Vevor | `1a86:7523` CH340 | `forward_info.serial.port` (socat) | `loki` + device `vevor`, Sprache `hpgl` |

### Mimaki wie FineCut: lokal per USB/IP (empfohlen unter Windows)

So plottet FineCut: Der Loki-Client haengt den Cutter per USB/IP an den PC
(`usbip port` zeigt `0a50:0001 -> usbip://<pi>:3240/1-1.3.1`). Windows bindet den
Mimaki-Treiber `mkusb` (Klasse `UsbPlotter`, Schnittstelle
`{fe05b407-0142-458b-ab3d-f7180561e884}`), FineCut schreibt MGL-IIc direkt dorthin.

Plot Cut macht dasselbe mit Transport `mimaki_usb` (`transport.MimakiUsbTransport`):
Geraetepfad aus `HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\{fe05b407-...}`,
`CreateFileW` + `WriteFile` in 4-KB-Bloecken. Feld `usb_path` im Profil leer = automatisch.
Illustrator/FineCut muessen dafuer nicht beendet werden; nur nicht gleichzeitig senden.

Vevor genauso: Der Loki-Client haengt den CH340 (`1a86:7523`, usbip `1-1.3.3`) an den
PC, Windows zeigt einen COM-Port (z. B. COM5). Profil `serial`, `serial_port: "auto"`
sucht den CH340 selbst, weil sich die COM-Nummer beim Anhaengen aendern kann.

Der Weg `loki` (`/api/plotcut/.../job`) geht ueber Lokis USB-Bridge und scheitert im
USB/IP-Modus mit 503 "USB 0a50:0001 nicht gefunden", weil usbip das Geraet haelt.

Die API ist ab Loki 1.5.0 da. Transport im Profil auf `loki` stellen, Host = Pi,
`device` = `id` aus `GET /api/plotcut/devices`.

HTTP-API (Client: `transport.LokiTransport`, Test: `tests/test_loki_transport.py`):

- `GET  http://<pi>:7576/api/plotcut/devices`
  → `{"devices":[{"id","name","kind","available","attached_to"}]}`
- `POST http://<pi>:7576/api/plotcut/devices/{id}/job`, Body = Rohbytes
  (`application/octet-stream`) → `{"ok":true,"bytes":N}`
- Fehler `{"detail":"..."}`: 404 API/Geraet fehlt, 409 belegt, 503 nicht geshared.

## Steuerkanal-Protokoll (VectorCraft)

Siehe `docs/control-protocol.md` im VectorCraft-Repo. Kurzfassung:

- Verbindung: TCP `127.0.0.1:7979`, nur loopback, keine Authentifizierung.
- Je Request eine JSON-Zeile: `{"id": 1, "method": "...", "params": {...}}\n`
- Antwort: `{"id": 1, "ok": true, "result": {...}}` oder `{"ok": false, "error": "..."}`
- Genutzte Methoden: `ui.inspect` (Ping), `engine.commands`, `document.inspect` (Auswahl,
  Ebenen, Pfad), `app.export` mit `format: "svg"`, `selectedOnly: true`, ohne `path`
  (liefert `dataBase64`), Rueckfall auf DXF.

## MGL-IIc / HP-GL (vereinfacht)

- `IN;`                Initialisieren
- `SPn;`               Werkzeug
- `VSn;`               Geschwindigkeit (cm/s)
- `FSn;`               Klingendruck (g)
- `!PTn;`              Klingenoffset (mm * 100), nur MGL-IIc
- `PU x,y;`            Pen Up (Leerfahrt) zu Schritt-Koordinate
- `PD x,y[,x,y...];`   Pen Down (schneiden)

Die Mimaki-spezifischen Bedingungsbefehle sind noch nicht am echten CG-60SR geprueft. Mit
"Schneidbedingungen mitsenden" = aus werden nur `IN`/`PU`/`PD` gesendet, und der Plotter
nutzt die Werte von seinem Bedienfeld.

## Start

Fuer Endnutzer die **Verknuepfung "Plot Cut"** auf dem Desktop bzw. im Startmenue (zeigt auf
`dist\Plot Cut.exe`). Keine .bat noetig.

1. "Plot Cut" starten. Das Panel liegt dann oben und als Tray-Icon. Kurzbefehl
   Strg+Alt+P = Plot.
2. Im Panel das Plotter-Profil waehlen (z. B. Mimaki CG-60SR oder Vevor).
3. In VectorCraft Schneidepfade auswaehlen, im Panel auf **Plot** klicken.
4. Ist der VectorCraft-Steuerkanal nicht aktiv, bietet das Panel an, VectorCraft
   automatisch mit `--control <port>` zu starten (`vc_launcher.py`). Pfad zu
   `vectorcraft.exe` wird gesucht (Standard `C:\Program Files\VectorCraft\vectorcraft.exe`)
   und ist im Setup einstellbar. Eine schon offene Instanz ohne Steuerkanal vorher schliessen.

Zum Entwickeln: `run.bat` (startet aus dem venv mit Python 3.12) und `start-vectorcraft.bat`.

## Entwicklung

- Python **3.12** im `.venv` (PySide6 6.12 unterstuetzt 3.14 noch nicht).
- App-Icon: `assets/logo.png` (Fenster, Tray, Panel) und `assets/logo.ico` (EXE).

## Eigenstaendiges Programm bauen (PyInstaller)

```
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onefile ^
  --name "Plot Cut" --paths . --collect-submodules plot_cut ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets ^
  run_app.py
```

Ergebnis: `dist\Plot Cut.exe` (~45 MB, enthaelt Python + PySide6). Einstieg ist `run_app.py`.
Danach Desktop- und Startmenue-Verknuepfung "Plot Cut.lnk" auf diese Datei anlegen.
Das Spec-File ist `Plot Cut.spec` (Icon nur unter Windows, unter macOS zusaetzlich ein
`.app`-Bundle). Ein veroeffentlichtes GitHub-Release startet `.github/workflows/release.yml`
und haengt die gebauten Programme an: `Plot-Cut.exe`, `Plot-Cut.dmg` (das `.app` darin)
und `Plot-Cut-linux`.

## Phase 2 (spaeter)

- Wasm-Object-Filter (Rust) nach Vorbild `crates/plugins/example`: Kontur/Offset,
  Entgitterlinien, "auf Cut-Ebene verschieben"; ausgeloest ueber
  `engine.execute plugin.dialog {id}` (Live-Vorschau auf der Zeichenflaeche).
- Medienbreite vom Plotter abfragen; Passermarken / ID Cut.
- Mimaki-Bedingungsbefehle anhand eines FineCut-Mitschnitts (Loki-Mitschnitt) verifizieren.
