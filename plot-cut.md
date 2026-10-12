# Plot Cut

Ein schwebendes Schneideplotter-Panel fuer VectorCraft im Stil von Mimaki FineCut. Es ahmt
den FineCut-Ablauf aus Adobe Illustrator nach: Auswahl aus VectorCraft holen, Plot- und
Plot-Out-Fenster mit Vorschau und Simulation anzeigen und die Schneidedaten (MGL-IIc oder
HP-GL / DMPL) ueber den Loki-PrintServer an einen von mehreren Plottern senden (z. B. Mimaki
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
mgl.py         ---- MGL-IIc / HP-GL / DMPL erzeugen (Sprache je Plotter-Profil)
   v
transport.py   ---- Loki-HTTP | TCP (socat am Pi) | COM-Port | Datei (.plt)
   v
Loki-PrintServer -> Plotter (Mimaki CG-60SR, Vevor, ...)
```

Die GUI (PySide6) sitzt obenauf:

- `ui/panel.py`            Werkzeugfenster im FineCut-Look, Profilauswahl, immer im Vordergrund
- `ui/plot_dialog.py`      [Plot]: Folienvorschau, Drehen, Spiegeln H/V, Kacheln, Passermarken
- `ui/plot_out_dialog.py`  [Plot Out]: Schneidbedingungen, Vorschau mit Farbcodes, Simulation, Senden
- `ui/setup_dialog.py`     Setup: VectorCraft, Plotter-Profile, Verbindung, Bedingungen, Favoriten
- `ui/preview.py`          gemeinsame Vorschau (Folie, Raster, Masse, Zoom/Pan)

## Datenfluss / Koordinaten

- VectorCraft exportiert SVG mit **einheitenlosem** `width`/`height` in **Punkten** (A4 =
  595.276 x 841.89). svgelements wuerde das als 96-dpi-px lesen (30 mm -> 22,5 mm). Darum
  rechnet `geometry._svg_scale` einheitenlose Werte als pt (25,4/72 mm) und Werte mit
  Einheit als CSS-px (25,4/96 mm). Regressionstest: `test_vectorcraft_svg_is_in_points`.
- Intern wird alles in Millimetern gefuehrt, y nach oben, Ursprung = Plotter-Nullpunkt.
- MGL-IIc: 0,025 mm als Ganzzahl-Schritte, 0,01 mm als Millimeter mit zwei Nachkommastellen.
  HP-GL/DMPL: 0,10 / 0,05 / 0,025 / 0,010 mm (XFCut: 254 / 508 / 1016 / 2032 pro Zoll).
- Bezierkurven werden mit `plotter.crv_res` (Standard 0,05 mm) zu Polylinien abgeflacht.
  Ein geschlossener Linienzug, der auf einem Kreis liegt, wird beim Schreiben als
  `AA` ausgegeben (MGL-IIc und HP-GL).

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
    (`OH;` an Mimaki-USB, COM oder TCP; ohne Antwort die Profilwerte),
    Schneiden... (-> Ausplotten), Beenden.
  - Tabelle mit ↔/↕: Blattgröße, Offset, Größe, Skalierung(%) (gekoppelt "—",
    ausser bei Verzerren), Kopieren X/Y als Raster, Kopierabstand X/Y,
    Rahmen (Haken + Abstand X/Y, wird mitgeschnitten). Darunter Gesamtmass;
    rot, wenn breiter als die Folie.
  - Tabs Layout / Kacheln Abstand / Passermarken. Layout: Drehen (90°),
    Bewegen (9 Positionen auf der Folie), Anpassen (proportional auf die Folie
    skalieren), Original Layout; Spiegeln H/V, Verzerren, Nullpunkt fest,
    WYSIWYG oder Ursprung, Kurvenaufloesung. Kacheln: Bahnen in Folienformat
    mit Ueberlappung und Haken je Kachel. Passermarken: aussen/innen, Groesse,
    Linienbreite, rund, extra.
  - Tabs Farbe / Ebene: Farbliste mit Haken, abgehakte Farben werden nicht geschnitten.
  Reihenfolge der Platzierung: drehen/spiegeln H+V, skalieren, an Ursprung
  (aus bei WYSIWYG), Rahmen, Bahnen, Kopienraster, Passermarken, dann
  Bewegen-Position + Offset (nicht bei Nullpunkt fest).
- Ausplotten (frueher "Plot Out") wie FineCut: Plot-Einstellung mit
  Plotter-Einstellung (keine Bedingungsbefehle), Auswahl-Einstellung (Preset aus
  `favorites`) oder Benutzerdefiniert (Werkzeug CT1/PEN/CT2-5/PIN/HLF, Geschwindigkeit/Andruck/Offset
  einzeln abwaehlbar = Wert am Plotter lassen). Bedingung je Farbe (Preset oder
  "Nicht schneiden", gespeichert in `conditions_by_color`). Optionen: Sortieren
  (Alle / Jede Farbe, Innen vor Aussen), Overcut, Mehrfachschnitt, nach jeder Farbe
  anhalten, Kopf in Parkposition, Endaktion (Ursprung / Folie vorschieben / stehen bleiben).
  Rechts: Schneiden, Abbrechen, Vorschau... (eigenes Fenster mit
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

### Schema Version 3 (aktuell)

```json
{
  "version": 3,
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
        "language": "mgl2",         // "mgl2" | "hpgl" | "dmpl"
        "sheet_width_mm": 610.0,
        "sheet_height_mm": 1000.0,
        "step_mm": 0.025,           // mgl2: 0.025 | 0.01; hpgl/dmpl: 0.10 | 0.05 | 0.025 | 0.010
        "crv_res": 0.05             // Kurvenflachheit in mm
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
        "send_conditions": true,    // SP/VS/FS/ZO mitsenden (aus condition_source abgeleitet)
        "condition_source": "custom", // "plotter" | "preset" | "custom" (Ausplotten)
        "preset": "",               // Name aus favorites bei "preset"
        "tool": 1,                  // FineCut SP: CT1=1 PEN=2 CT2=3 CT3=4 PIN=5 HLF=6 CT4=7 CT5=8
        "use_speed": true,          // false = VS nicht senden
        "use_pressure": true,       // false = FS nicht senden
        "use_offset": true,         // false = ZO nicht senden (nur mgl2)
        "sort_mode": "all",         // "all" | "color"
        "park": true,               // Kopf nach dem Schnitt hinter das Motiv
        "park_mm": 20.0,
        "end_action": "stay",       // "origin" | "feed" | "stay"
        "feed_mm": 20.0,
        "extra_passes": 0,
        "pause_per_color": false
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
    //   "rotate_index": 0, "mirror": false, "mirror_h": false, "mirror_v": false,
    //   "wysiwyg": false, "distort": false, "fixed_origin": false,
    //   "copies_x": 1, "copies_y": 1, "gap_x": 10, "gap_y": 10,
    //   "offset_x": 0, "offset_y": 0, "anchor": [0, 0],
    //   "frame_on": false, "frame_x": 10, "frame_y": 10, "disabled_colors": [],
    //   "tile_on": false, "tile_overlap": 0, "tile_skip": [],
    //   "marks_on": false, "marks_inner": false, "marks_size": 10, "marks_line": 1,
    //   "marks_round": false, "marks_extra": false
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
- **v2 -> v3**: In MGL-IIc-Profilen werden die alten Werkzeugnummern CT2=2 und CT3=3
  einmal auf FineCut CT2=3 und CT3=4 gehoben. Favoriten mit 2 bzw. 3 ebenso.

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

Vevor ist eine Haendler-Marke, kein eigenes Plotter-Protokoll. Handbuch und
Produkttext nennen die Sprachen **DMPL/HPGL**, die USB-Buchse erscheint als
**USB-SERIAL CH340** (kein eigener USB-Treiber wie `mkusb`). Am Geraet steht
meist Baud **9600**; die Schrittweite ist **0,0245 mm**. Das ist praktisch
dieselbe HP-GL-Aufloesung wie `STEPS_PER_MM = 40` (0,025 mm). Einzelne Modelle
weichen ab: der KW-780A spricht seriell mit 38400 und kann HP-GL auch roh ueber
USB als Drucker nehmen, beim SK-720 wurde in Inkcut 115200 probiert. Die
Sprache am Display und die Baudrate in Plot Cut muessen uebereinstimmen.

XFCut Pro legt Vevor als benannte Profile auf denselben allgemeinen Stapel.
Der Befund steht im Abschnitt "XFCut und generische Plotter".

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
- `ZOn;`               Klingenoffset (mm, eine Nachkommastelle), nur MGL-IIc
- `PU x,y;`            Pen Up (Leerfahrt)
- `PD x,y[,x,y...];`   Pen Down (schneiden)
- `PG;`                Seite ausgeben, HP-GL bei Endaktion Ursprung
- DMPL: Kopf `;:H A L0 ECN U `, Fahrt `U%d,%d`, Schnitt `D%d,%d`

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

## FineCut am CG-60SR (Stand 2026-10-12)

Statischer Vergleich, nichts wurde ausgefuehrt und nichts an den Plotter geschrieben.
Quellen auf diesem PC:

- `C:\Program Files\Adobe\Adobe Illustrator 2026\Plug-ins\Mimaki FineCut\FCInfo\CG60SRMachineInfo.json`
  (FineCut-Maschinenprofil, `Machine.Ver` 9.1.0)
- `...\Mimaki FineCut\Mimaki FineCutAI30.aip` (Plug-in, Befehlstabelle als Zeichenketten)
- `C:\Program Files\Mimaki\MimakiDeviceController\MmkCutCtrl.dll`
  (Ghidra 12.1.4 ueber REA, SHA-256 `3864ea15ec28b14b052a46552541292630b5392a9d841f9244c353c31d892f64`)
- `...\Mimaki FineCut\Lib\LibHpglLas.dll` ist **keine** Mimaki-Schnittbibliothek.
  Ghidra zeigt Gravotech Marking, Lasergeraete `L_Solution_*`, Kamera und Marker.
  Befehle dort (`!1B`, `!IG`, `!IO`, `!PS`, `!TP`) gelten nicht fuer den CG-60SR.

Der USB-Treiber (`mkusb` 1.1 / `mkusb20` 2.0 unter `C:\Program Files (x86)\Mimaki\Device Driver`)
wurde nicht dekompiliert. Fuer den CG-60SR setzt das Profil nur USB 1.1.

### Was das Profil fuer den CG-60SR einschaltet

Beobachtet in `CG60SRMachineInfo.json`:

- Ursprung `RightBottom`. Plot Cut macht das fuer `mgl2` bereits.
- Verbindung: `USB11` true, `USB20` false, `LAN` false, `Serial` false.
  Default `USB11`. Serielle Defaults stehen trotzdem im Profil (9600, 8 Bit, keine Paritaet, Hardware-Handshake), sind aber aus.
- Geschwindigkeit 1–120 cm/s, Standard 30. Andruck 1–500 g, Standard 100.
  Plot Cut: Geschwindigkeit 1–120, Andruck 1–500.
- Aufloesung `MGL-IIc`: `0.025mm` und `0.01mm`. Zusaetzlich `MGL-Ic`: `0.05mm` und `0.1mm`.
  Plot Cut: 0,025 mm als Ganzzahl-Schritte und 0,01 mm als `PU%.2f,%.2f;`.
- Annaeherung: Linie oder Bogen. Volle Kreise gehen als `AA` (Mittelpunkt, 360 Grad)
  an MGL-IIc und HP-GL. Andere Kurven werden nach `crv_res` zu Geraden. `ZC`
  fuer Teilboegen fehlt weiter.
- Werkzeuge, Wert ist die Nummer im `SP`-Befehl:

  | Name | Nummer |
  |---|---|
  | CT1 | 1 |
  | PEN | 2 |
  | CT2 | 3 |
  | CT3 | 4 |
  | PIN | 5 |
  | HLF | 6 |
  | CT4 | 7 |
  | CT5 | 8 |

  Plot Cut nutzt dieselbe Tabelle. Alte gespeicherte 2 und 3 werden beim Laden auf 3 und 4 gehoben.

- Funktionen an: Blattgroesse lesen, Rahmen, Bahnen (Tiling), Perforation.
- Ausgabe-Optionen an: Folienvorschub, Kopf abheben, Ursprung erneuern, Sortieren,
  Standardbedingung benutzen.
- Passermarken an: aussen und innen. Standard aussen. Groesse 4–40 mm, Standard 10.
  Linienbreite 0,3–1 mm, Standard 1. Zusaetzlich Marke, runde Fuellung und Rechtecklinie.
  Erkennung: einzelne Marke oder Mehrfachkopie (bis 99 horizontal, 9999 vertikal).
- Funktionen aus, fuer diesen Plotter nicht nachbauen: Druck-und-Schnitt, ID-Cut,
  RasterLink, Kamera, Fraesen, Laser, Flachbett, Favoriten, Kantenschnitt, Schnittmodus.
  Favoriten hat Plot Cut trotzdem. Das ist zusaetzlich, nicht ein FineCut-Ersatz.

### Befehlstabelle im Plug-in

Im AIP liegt eine Format-Tabelle fuer mehrere Maschinen nebeneinander. Welche Zeile
der CG-60SR nimmt, ist daraus nicht abgeleitet. Sichtbare MGL-nahe Muster, die Plot Cut
heute teilweise schreibt:

- Start nicht nur `IN;`, sondern `IN;IP0,0,1,1;` und `IN;IP0,0,1,1;JT19,20;`
- Koordinaten als Kommazahl: `PU%.2f,%.2f;` und `PD%.2f,%.2f;` (passt zur 0,01-mm-Stufe,
  ist aber nicht als der gewaehlte CG-60SR-Pfad bewiesen)
- Stift und Bedingung: `SP%d;`, `JT%d,%d;`, `VS%d,%d;`, `JG2;FS%d,%d;`, `ZO%.2f;`
  Plot Cut sendet `SP`, `VS`, `FS` und `ZO` (eine Nachkommastelle). `JT`/`JG2`
  fehlen. `!PT` steht in dieser Tabelle nicht und wird nicht geschrieben.
- Weitere Namen in derselben Tabelle: `FL`, `ZF`, `ZX`, `ZC`, `OH;`, `JO;`, `JS`, `JC;`,
  `JD`, `JR`, `JI`, `JN`
- Daneben liegen Formate anderer Geraete (G-Code `G01`, Laser `LC`/`VL`). Die nicht
  fuer den CG-60SR verwenden.

Das Plug-in schreibt vorher eine Spool-Datei `FCCommand.dat` bzw.
`FineCutSpool.tmp` unter `\Mimaki\FineCut\AI%d\`. Kommentare darin, als Formatstrings
beobachtet:

- `%%MimakiCommentVersion`, `%%MimakiDataType`, `%%MimakiCopy`
- `%%MimakiHeadWithdrawal: %d %d %d %f %d %f`
- `%%MimakiSheetFeed: %d`
- `%%MimakiAutoCut`
- `%%MimakiTombo`, `%%MimakiTomboBackside`, `%%MimakiTomboBoundingBox`, `%%MimakiTomboSeparation`

Das ist die Zwischenablage von FineCut, nicht belegt als die Bytes, die der CG-60SR
am USB sieht.

### Device Controller

`MmkCutCtrl.dll` baut Schnittdaten und protokolliert diese Schritte. Zum CG-60SR-Profil
passen davon Blattvorschub, Ursprung und Kopfbewegung. Passermarken-Befehle gehoeren
hier zum Controller; das CG-60SR-Profil hat Druck-und-Schnitt und RasterLink aus,
Passermarken im Plug-in aber an.

Beobachtete Schritt-Namen:

- `kInitialCommand`, `kOriginCommand`, `kOriginSetCommand`, `kInputWindowCommand`
- `kSheetFeedCommand` (ein Mass), `kPenUpCommand` (Kopfbewegung, zwei Masse)
- `kDataEndCommand`, `JoinArcCommand`, `kSplineDimensionCommand`
- `kTomboReviseCommand` (zwei Masse), `kTomboDetectionCommand`, `kTomboRepeatCommand`
- `kAutoCutCommand`, `kAutoCutPositionCommand`, `kSplitCutCommand`
- `PinchRollerChange`, `GQ`, `QK` (Farbbalken und Schnittmodus)

Auto-Cut und Split-Cut stehen im CG-60SR-Profil auf falsch.

### Nachbau (Stand 2026-10-12, in Plot Cut)

Umgesetzt: Werkzeugnummern, Geschwindigkeit 1–120, Andruck 1–500, Aufloesung 0,025 und
0,01 mm, Start `IN;IP0,0,1,1;`, Offset `ZO`, Blattgroesse per `OH;`, Endaktion
(Ursprung / Vorschub / stehen bleiben), Kopf abheben, Bahnen, Rahmen, Passermarken
als Schnittpfade, WYSIWYG oder Ursprung, Spiegeln H/V, Kurvenaufloesung als
Segmentlaenge, volle Kreise als `AA`.

### Bogenbefehl (Ghidra 12.1.4, 2026-10-12)

`JoinArcCommand` ist `FUN_18000d590` in `MmkCutCtrl.dll`, aufgerufen aus
`FUN_18000a0e0`. Die Funktion liest Zwischenzeilen `ZCAA` (Werkzeug plus acht
Koordinaten) und schreibt an den Plotter:

- geschlossener Kreis, Startpunkt gleich Endpunkt: `AA%.2f,%.2f,%.2f;`
  Mittelpunkt X, Mittelpunkt Y, Winkel fest `360.0` (Konstante bei `0x18003db50`).
  Das ist HP-GL Arc Absolute: vom aktuellen Punkt um den Mittelpunkt.
  Plot Cut schreibt das fuer erkannte volle Kreise, bei MGL-IIc mit 0,01 mm als
  `AA%.2f` und sonst als Ganzzahl-Schritte. Im Uhrzeigersinn ist der Winkel `-360`.
  DMPL bleibt bei Geraden.
- sonst: `ZC%.2f,%.2f,%.2f,%.2f;` mit zwei Punkten aus der zusammengefassten Kette.
  Welche der vier Zahlen Mittelpunkt, Zwischenpunkt oder Ende ist, ist aus diesem
  Lauf nicht fest. Deshalb schreibt Plot Cut `ZC` noch nicht.
- Aneinanderhaengende Boegen derselben Klinge werden zu einem Bogen, wenn die
  Mittelpunkte naeher als `Radius * 0.0001` liegen (`FUN_18000e1a0`).

`AA%f,%f,%f;` und `ZCAA%d,%.2lf,...` liegen in derselben Tabelle fuer andere
Formatzeilen. Welche Zeile der CG-60SR nimmt, bleibt offen.

Weiterhin ohne Bytefolge, deshalb nicht geraten: Perforation, Tombo-Erkennung,
`JT`/`JG2`. `!PT` wird nicht mehr geschrieben.

Offen, bis ein echter Auftrag mitgelesen wird: welche Formatzeile der CG-60SR nimmt,
ob die Koordinaten als Schritt oder als Millimeter mit zwei Nachkommastellen rausgehen,
und ob der Illustrator-Pfad den Device Controller ueberhaupt benutzt.

## XFCut und generische Plotter (Stand 2026-10-12)

Statisch gelesen, nichts ausgefuehrt und nichts an einen Plotter geschrieben.
Ghidra 12.1.4. Die volle REA-Suche ueber alle Funktionen ist an der Analyse
der 16-MB-DLL abgebrochen. Der ausgewertete Lauf ist Headless-Ghidra mit
abgeschalteten Decompiler-Analysen, danach Dekompilat nur der Funktionen,
die die Befehlszeichenketten benutzen.

Quellen auf diesem PC:

- `C:\Program Files\Adobe\Adobe Illustrator 2025\Plug-ins\XFCutAdobePlugin2025.aip`
  (132608 Bytes, SHA-256 `64db0647abb95c8da6417a4526fbce53cb7cf321eae8d6ef9e04e4b91e43ddf9`).
  Bruecke zu Illustrator. Keine Plotterbefehle.
- `C:\Program Files\XFCut Pro\XFCutPro.dll`
  (16171784 Bytes, SHA-256 `04af8f82e100eae21e1428eb105b6120303f95a910ecc36254dc3cfdf004c5da`).
  Ghidra: 33020 Funktionen. Die Befehlsfunktionen heissen dort `FUN_...`,
  weil der RTTI-Analysator die Klassennamen nicht auf die Funktionen geschrieben hat.
- `C:\Program Files\XFCut Pro\XFCut Pro.exe` (25818376 Bytes) wurde nicht dekompiliert.
  Dieselbe Linie: Sure Cuts A Lot, Copyright 2008-2025 Craft Edge und 2023-2025 XFCut.com.
  Sprachdateien `Lang\SCAL6_*.dll`.
- Hilfe unter `C:\Program Files\XFCut Pro\Hints\Help\` beschreibt die Fenster.
  `Pens\standard.pens` enthaelt nur Farbnamen.

### Was fertig belegt ist, und was offen bleibt

Belegt ist der allgemeine Befehlssatz und die Profilstruktur. Offen bleibt,
welche der Vevor-Klassen welchen Kopf schreibt. Dafuer braeuchte es die
Zuordnung Klasse zu Funktion. Die hat dieser Lauf nicht geliefert. Eine
komplette Dekompilation aller 33020 Funktionen ist kein naechster Schritt.

### Profile

RTTI-Klassen, aus den Typnamen der DLL:

- Einstellungen: `Vevor`, `VevorSk`, `VevorTT`, `VevorKICS`, `VevorSmart`
- Geraet: `Vevor`, `VevorSmart`
- USB-Klasse nur `VevorSmart`. Das Profil `Vevor` haengt am allgemeinen COM-,
  CH375- und USB-Stapel (`GenericComIO`, `GenericCh375`, `GenericUsb`).
- Passermarken: `RegMarksVevorCircle`, `RegMarks_AutoScanVevorSmart`
- Daneben die allgemeinen Profile `PlotterGenericHpgl` und `PlotterGenericDmpl`,
  Anzeigenamen "Generic HPGL" und "Generic DMPL".

Anzeigenamen im selben Block wie `Vevor`: `KI`, `1350`, `KH-A`, `KI-CS`, `TT`.
Getrennt davon `Vevor Smart` mit `Smart1` bis `Smart4`. Welcher Name zu welcher
Klasse gehoert, ist aus der Nachbarschaft der Zeichenketten geschlossen, nicht
aus einem Querverweis.

Gespeichertes Profil, aus dem Dekompilat der Schreibfunktion `FUN_18006f390`:

- `cmd_lang`: `0` custom, `1` hpgl, `2` dmpl, `3` gpgl
- letzte Verbindung: `usb`, `serial`, `bluetooth`, `parallel`, `printer`,
  `local_network`, `tcpip`, `bluetoothle`, `file`, `saga_arms_server`
- weitere Felder in demselben Block: `baud`, `crv_res`, `jog_n`, `jog_f`,
  `bl_off` / `bl_ovi` (Klingenoffset), `bl_ov` (Overcut), `multic` (Mehrfachschnitt),
  `spc` / `spu` / `prs` (Geschwindigkeit und Andruck), `use_softsp`, `cutmode`,
  `aftercut`, `aftercut_adv`

Baud-Werte, die die Oberflaeche anbietet: 4800, 9600, 14400, 38400, 57600, 115200.
Plot Cut laesst Baud im Setup frei (Vevor-Standard 9600). Das passt zum ueblichen Display.

Aufloesung, die `FUN_180081a60` in die Liste schreibt, in Einheiten pro Zoll:

| Eintrag | Schritt |
|---|---|
| 254 (0.10 mm) | 10 pro mm |
| 508 (0.05 mm) | 20 pro mm |
| 1016 (0.025 mm) | 40 pro mm |
| 2032 (0.010 mm) | 100 pro mm |

`1016` pro Zoll ist `STEPS_PER_MM = 40` in `plot_cut/mgl.py`. Die 0,0245 mm aus
dem Vevor-Handbuch liegen auf derselben HP-GL-Stufe.

### Befehlssaetze im Dekompilat

Dieselben Builder enthalten HP-GL und DMPL nebeneinander. Stift hoch/runter
schaltet am Sprachfeld: Wert `1` schreibt `PU%d,%d;` und `PD%d,%d;`, Wert `2`
schreibt DMPL `U%d,%d` bzw. `D%d,%d`. Ein weiteres Flag in einzelnen Buildern
waehlt `U%d,%d ` mit Leerzeichen. Koordinaten sind Ganzzahlen.

Koepfe, jeder in einer eigenen Funktion. Welches Vevor-Profil welchen nimmt,
ist offen:

- HP-GL: `IN;PA;SP1;` und `IN;PA;US%d;VS%d;!FS%d;`
- DMPL: `;:H A L0 ECN U ` und `;:H A L0 ECN U P1;US%d;VS%d;!FS%d;`
- anderer HP-GL-Kopf: `IN;SP1;US%d;VS%d;FS%d;`
- Start mit Ende in derselben Funktion: `IN;PA;US%d;VS%d;` und danach `PU0,0;PG;`
- Geschwindigkeit und Andruck nur, wenn das Software-Flag gesetzt ist.
  Eine Funktion schreibt `US%d;` `VS%d;` `!FS%d;`, die Nachbarfunktion
  `US%d;` `VS%d;` `FS%d;`. `US` ist in diesem Kopf der zweite Geschwindigkeitswert.

Andere Geraete in derselben DLL, nicht in das Vevor-Profil uebernehmen:

- Mimaki-nahe Bedingung: `TB25,%d,%d;CT1;`, `TB26,0,%d,%d;CT1;`,
  `IN;TB25,%d,%d;CT1;`, `IN;TB26,%d,%d;CT1;`, `SC1;MN4;TB25;%d,%d;CT1;`
- Roland-nah: `.R99:IN;PA;AB;SP0;`, `PU0,500;PU0,0;PG;`,
  `.R99:IN;VS21;PA;PU0,500;PU500,500;PG;`
- `@PJL DO CROPMARK %d,%d,%d,%d,%d` und die Zeichenkette
  `@PJL SET CAMMGL3 = !FS,ON`

Plot Cut schreibt fuer HP-GL: `IN;PA;`, `PU`, `PD`, `SP`, `VS`, `FS`, und bei
Endaktion Ursprung `PU0,0;PG;`. `US` und `!FS` fehlen. DMPL: `;:H A L0 ECN U `
und `U`/`D`. `!PT` kommt in den XFCut-Befehlszeichenketten nicht vor.

### Fenster, aus der Hilfe

Das sind Bedienfunktionen, keine eigenen Plotterbefehle:

- Schnittmodus WYSIWYG oder an den Ursprung schieben. Spiegeln horizontal und vertikal.
- Geschwindigkeit und Andruck aus der Software sind optional. Sonst gelten die Werte am Geraet.
- Nach dem Schnitt: zum Ursprung zurueck, Material um ein Mass vorschieben, oder stehen bleiben.
- Halter Klinge oder Stift. Klingenoffset, Overcut, Mehrfachschnitt.
- Kopien in Zeilen und Spalten. Bahnen, wenn das Motiv groesser als die Folie ist.
- Schnitt nach Farbe: alle Farben in einem Auftrag, oder nach jeder Farbe anhalten.
- Ebenen-Namen, die XFCut aus Illustrator liest: `SCAL.DRAW` (Stift),
  `SCAL.CUTONLY`, `SCAL.PRINTONLY`, `SCAL.COLORLAYERKEY`.
- Passermarken nur, wenn das gewaehlte Geraet Print-and-Cut kann.
  Groesse, Linienstaerke, Abstand. Jog normal und mit Umschalt schnell.
- Aufloesung wird an einem Quadrat von 1 Zoll mal 1 Zoll kalibriert.

### Nachbau (Stand 2026-10-12, in Plot Cut)

Umgesetzt: DMPL als dritte Sprache (`U`/`D`, Kopf `;:H A L0 ECN U `), HP-GL-Start
`IN;PA;`, Ende `PG;` bei Ursprung, Aufloesungsstufen 0,10 / 0,05 / 0,025 / 0,010 mm,
`VS`/`FS` nur mit Haken, Mehrfachschnitt, Endaktionen, runde Passermarken als Pfade.

`!FS`, Mimaki `TB` und Roland `.R99` bleiben aus. Baud bleibt die freie Zahl im Setup
(Standard 9600). Ein Scan-Befehl fuer Vevor Smart fehlt weiter.

## Phase 2 (spaeter)

- Wasm-Object-Filter (Rust) nach Vorbild `crates/plugins/example`: Kontur/Offset,
  Entgitterlinien, "auf Cut-Ebene verschieben"; ausgeloest ueber
  `engine.execute plugin.dialog {id}` (Live-Vorschau auf der Zeichenflaeche).
- `ZC` erst, wenn die vier Zahlen belegt sind.
  Perforation und Tombo-Erkennung erst mit Bytefolge. `!FS` erst nach einem
  Vevor-Mitschnitt.
