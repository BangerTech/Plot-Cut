"""Findet die VectorCraft-Programmdatei und startet sie mit Steuerkanal.

So muss der Benutzer keine .bat ausfuehren: Ist der Steuerkanal nicht offen,
kann das Panel VectorCraft selbst mit ``--control <port>`` starten.
"""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

# Uebliche Installationsorte (Windows).
_CANDIDATES = [
    r"C:\Program Files\VectorCraft\vectorcraft.exe",
    r"C:\Program Files (x86)\VectorCraft\vectorcraft.exe",
]


def find_vectorcraft(explicit: str | None = None) -> str | None:
    """Gibt den Pfad zu vectorcraft.exe zurueck, oder None."""
    if explicit and Path(explicit).exists():
        return explicit

    for cand in _CANDIDATES:
        if Path(cand).exists():
            return cand

    # LocalAppData / Programs durchsuchen (Portable-Installationen)
    roots = [
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"),
    ]
    for root in roots:
        if not root:
            continue
        base = Path(root)
        if not base.exists():
            continue
        try:
            for hit in base.glob("**/vectorcraft.exe"):
                return str(hit)
        except OSError:
            continue
    return None


def control_port_open(host: str, port: int, timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def launch_with_control(exe_path: str, port: int, extra_args: list[str] | None = None) -> bool:
    """Startet VectorCraft mit ``--control <port>`` (losgeloest vom Panel)."""
    if not Path(exe_path).exists():
        return False
    args = [exe_path, "--control", str(port)]
    if extra_args:
        args.extend(extra_args)
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    try:
        subprocess.Popen(  # noqa: S603
            args,
            creationflags=flags,
            close_fds=True,
            cwd=str(Path(exe_path).parent),
        )
        return True
    except OSError:
        return False
