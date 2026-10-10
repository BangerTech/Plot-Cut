# Plot Cut

![Plot Cut](assets/logo.png)

A FineCut-style cutting panel for [VectorCraft](https://github.com/storytold/vectorcraft). It takes the current selection, shows a sheet preview, and sends MGL-IIc or HP-GL to a cutter.

Profiles included: **Mimaki CG-60SR** (MGL-IIc, origin bottom-right) and **Vevor** (HP-GL, origin bottom-left).

```
VectorCraft (--control 7979)
        │  selection as SVG
        ▼
     Plot Cut  →  cutter
```

VectorCraft plug-ins cannot draw their own panel or open a network connection, so Plot Cut is a separate always-on-top window beside the app.

On Windows with [Loki-PrintServer](https://github.com/BangerTech/Loki-PrintServer), plotting works the same way FineCut does: the Loki client attaches the cutter to this PC over USB/IP, and Plot Cut writes to the local device.

| Plotter | Attach in the Loki client | Plot Cut connection |
|---|---|---|
| Mimaki CG-60SR | USB/IP (`0a50:0001`, driver `mkusb`) | **Mimaki USB (local, like FineCut)** |
| Vevor (CH340) | USB/IP (`1a86:7523`) | **COM port**, `auto` finds the CH340 |

Illustrator and FineCut do not have to be closed. Do not send from both programs at the same time.

The Loki HTTP job API (`POST /api/plotcut/devices/{id}/job`) is still available as transport `loki`. While a cutter is attached over USB/IP, that path cannot see the device.

## Requirements

- Windows 10/11
- [VectorCraft](https://getartcraft.com/apps/vectorcraft) (desktop)
- For a Mimaki or Vevor on the Pi: Loki client on this PC, cutter attached
- Python 3.12 only if you run from source (PySide6 does not support 3.14 yet)

## Getting started

End users: start **Plot Cut** (`dist\Plot Cut.exe`, or the desktop shortcut). No Python install needed.

From source:

```bat
git clone https://github.com/BangerTech/Plot-Cut.git
cd Plot-Cut
run.bat
```

`run.bat` creates a `.venv` on first run, installs dependencies, and opens the panel.

1. Start VectorCraft with the control channel: `start-vectorcraft.bat`  
   (or Plot Cut offers to launch it with `--control 7979` on the first plot)
2. Choose the plotter in the panel (Mimaki CG-60SR / Vevor)
3. Select the cut paths in VectorCraft
4. **Plot** → place the job on the sheet → **Schneiden...** → **Schneiden**

Panel shortcut: `Ctrl+Alt+P`.

Build the standalone program:

```bat
.venv\Scripts\python.exe -m PyInstaller --noconfirm "Plot Cut.spec"
```

Output: `dist\Plot Cut.exe`. The window and taskbar icon is `assets/logo.ico`.

## What the windows do

**Plot** (right-hand bar, FineCut layout): sheet size, offset, size and scale, copies on X and Y, frame, rotate, move, fit, mirror. The **Farbe** tab turns colors on or off.

**Ausplotten**: plotter settings, a saved preset, or custom speed / pressure / offset (each can be left to the cutter). Options cover sort order, overcut, and parking the head. **Vorschau...** opens direction, order, travel moves, and the simulation.

## Setup / connection

Open **Setup** from the panel.

| Transport | Use when |
|---|---|
| `mimaki_usb` | Mimaki on this PC via the Loki client (recommended) |
| `serial` | Vevor or another COM plotter. `auto` picks a CH340 |
| `loki` | HTTP job API on the Pi (USB bridge, not USB/IP) |
| `tcp` | raw TCP, e.g. socat port 7580 |
| `file` | write a `.plt` file, nothing is sent |

Settings live in `%APPDATA%\PlotCut\settings.json`. Schema and internals: [`plot-cut.md`](plot-cut.md).

## Development

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m plot_cut.main
```

## License

See the repository. VectorCraft is independent of Adobe. FineCut and Mimaki are trademarks of their respective owners. Plot Cut is an independent project and is not affiliated with or endorsed by Mimaki.
