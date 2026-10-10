# Plot Cut

A FineCut-style cutting panel for [VectorCraft](https://github.com/storytold/vectorcraft). It reads the current selection, shows a sheet preview and cut simulation, then sends MGL-IIc or HP-GL to a plotter — through [Loki-PrintServer](https://github.com/BangerTech/Loki-PrintServer) or directly (TCP / serial / file).

Multiple plotter profiles are supported, for example **Mimaki CG-60SR** (MGL-IIc) and **Vevor** (HP-GL).

```
VectorCraft (--control 7979)
        │  selection as SVG
        ▼
     Plot Cut          →  Loki-PrintServer  →  plotter
```

VectorCraft plug-ins cannot draw their own panel or use the network. Plot Cut therefore runs as a separate always-on-top window next to the app.

## Requirements

- Windows 10/11
- [VectorCraft](https://getartcraft.com/apps/vectorcraft) (desktop)
- Python 3.12 for development (PySide6 does not support 3.14 yet)
- Optional: [Loki-PrintServer](https://github.com/BangerTech/Loki-PrintServer) on a Raspberry Pi so plotters are available on the network

## Getting started

```bat
git clone https://github.com/BangerTech/Plot-Cut.git
cd Plot-Cut
run.bat
```

`run.bat` creates a `.venv` on first run, installs dependencies, and starts the panel.

1. Start VectorCraft with the control channel: `start-vectorcraft.bat`  
   (or Plot Cut will offer to launch it with `--control 7979` on the first plot)
2. Choose the plotter in the panel (Mimaki CG-60SR / Vevor / …)
3. Select the cut paths in VectorCraft
4. **Plot** → check the sheet → **Plot Out** → **Plot (send)**

Panel shortcut: `Ctrl+Alt+P`.

Standalone `.exe` (no Python required on the target machine):

```bat
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean "Plot Cut.spec"
```

Output: `dist\Plot Cut.exe`.

## Setup / connection

In the panel, open **Setup**:

| Transport | Use when |
|---|---|
| `loki` | Send raw bytes over HTTP to Loki (`POST /api/plotcut/devices/{id}/job`) |
| `tcp` | socat port on the Pi (e.g. 7580) |
| `serial` | local COM port (including one provided by the Loki client) |
| `file` | test only: writes a `.plt` file |

Default for the first test: **file**. Inspect the output, then switch to Loki / TCP / COM.

The Loki API Plot Cut expects is specified in [`LOKI-KI-AUFTRAG.md`](LOKI-KI-AUFTRAG.md) (against Loki-PrintServer **1.4.16**). Loki does **not** generate plotter commands.

Until that API exists on the Pi:

- **Vevor** (CH340): use transport `tcp` and the socat port from the Loki dashboard (`7580+`, also in `GET /api/devices/{bus_id}/forward` → `serial.port`).
- **Mimaki CG-60SR** (VID `0x0A50`, raw USB, no tty): needs the new `/api/plotcut` job path through Loki’s existing USB bridge. Do not treat it as a COM port. If FineCut has the cutter via USB/IP, detach it in the Loki client first.

Illustrator + FineCut over Loki must keep working unchanged.

## Development

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m plot_cut.main
python -m pytest -q
```

Internals and the settings schema: [`plot-cut.md`](plot-cut.md).

## License

See the repository. VectorCraft is independent of Adobe. FineCut and Mimaki are trademarks of their respective owners; Plot Cut is an independent project and is not affiliated with or endorsed by Mimaki.
