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

- Helle Folie (Rolle ab y = 0 nach oben, Breite aus dem Profil), adaptives mm-Raster,
  gruener Nullpunkt, Mass "B x H mm" unter dem Objekt.
- Plot: Objekt mit transparenter Originalfarbe und schwarzer Schnittkontur.
- Plot Out (FineCut-Konvention): schwarz = gegen Uhrzeigersinn, rot = im Uhrzeigersinn,
  gelb gestrichelt = Leerfahrt, blaue Reihenfolge-Nummern, Pfeile, gruener Kopf in der
  Simulation.
- Mausrad = Zoom um den Cursor, Ziehen = verschieben, Doppelklick / "Einpassen" =
  auf Objekt einpassen, "Ganze Folie" = ganze Folienbreite.

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
        "kind": "loki",             // "loki" | "tcp" | "serial" | "file"
        "host": "192.168.1.50",     // Raspberry Pi mit Loki
        "loki_port": 7576,          // Loki-HTTP-API
        "device": "mimaki-cg60sr",  // Loki-Geraete-id
        "port": 7580,               // nur kind=tcp (socat)
        "serial_port": "COM3",      // nur kind=serial
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
        "send_conditions": true     // SP/VS/FS/!PT mitsenden
      },
      "conditions_by_color": {
        // "#RRGGBB": { "tool": 1, "speed": 30, "pressure": 100, "offset": 0.3, "enabled": true }
      }
    },
    "Vevor": { "...": "gleiche Struktur, language hpgl, 720 mm, 20 cm/s, 80 g, 0.25 mm" }
  },
  "favorites": {
    // "Name": { ...wie defaults... }
  },
  "per_file": {
    // "C:/pfad/zeichnung.vectorcraft": { "copies": 1, "rotate": 0, "mirror": false, ... }
  },
  "ui": { "panel_geometry": "..." }
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
| 7576 | FastAPI + Dashboard. Plot Cut: `/api/plotcut/*` (noch zu bauen) |
| 7580+ | socat Serial-over-TCP (Vevor CH340 `1a86:7523`) |
| 631 | CUPS / IPP |

| Plotter | USB | Loki-Weg | Plot-Cut-Profil |
|---|---|---|---|
| Mimaki CG-60SR | VID `0x0A50`, Vendor-USB, kein tty | `usb_bridge.py` Raw-USB (Bulk); nicht `usbserial` | `loki` + device `mimaki-cg60sr`, Sprache `mgl2` |
| Vevor | `1a86:7523` CH340 | `forward_info.serial.port` (socat) | `loki` + device `vevor`, Sprache `hpgl` |

FineCut und Plot Cut koennen **nicht gleichzeitig** denselben Mimaki halten: USB/IP-Attach
→ Loki liefert `409` / `available: false`. Im Loki-Client vorher trennen.

Solange `/api/plotcut` auf dem Pi fehlt, bleibt Transport **file** oder **tcp** auf den
sichtbaren socat-Port des Vevor (Dashboard / `GET /api/devices/{bus_id}/forward`).

Geplante HTTP-API (Client: `transport.LokiTransport`, Test: `tests/test_loki_transport.py`):

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
- Tests: `.venv\Scripts\python.exe -m pytest -q`

## Eigenstaendiges Programm bauen (PyInstaller)

```
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onefile ^
  --name "Plot Cut" --paths . --collect-submodules plot_cut ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets ^
  run_app.py
```

Ergebnis: `dist\Plot Cut.exe` (~45 MB, enthaelt Python + PySide6). Einstieg ist `run_app.py`.
Danach Desktop- und Startmenue-Verknuepfung "Plot Cut.lnk" auf diese Datei anlegen.

## Phase 2 (spaeter)

- Wasm-Object-Filter (Rust) nach Vorbild `crates/plugins/example`: Kontur/Offset,
  Entgitterlinien, "auf Cut-Ebene verschieben"; ausgeloest ueber
  `engine.execute plugin.dialog {id}` (Live-Vorschau auf der Zeichenflaeche).
- Medienbreite vom Plotter abfragen; Passermarken / ID Cut.
- Mimaki-Bedingungsbefehle anhand eines FineCut-Mitschnitts (Loki-Mitschnitt) verifizieren.
