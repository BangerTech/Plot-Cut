"""Protokoll der Schnitte. Keine Datenbank, Textdateien neben den Einstellungen.

Eine Datei pro Tag unter ``%APPDATA%\\PlotCut\\logs``. Beim Schreiben fallen
Dateien weg, die aelter als ``KEEP_DAYS`` Tage sind.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from .settings import settings_dir

KEEP_DAYS = 7
MAX_BODY = 80_000


def log_dir() -> Path:
    path = settings_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def purge_old(directory: Path, now: datetime | None = None, keep_days: int = KEEP_DAYS) -> None:
    """Loescht ``plot-cut-JJJJ-MM-TT.log``, sobald das Datum ``keep_days`` zurueckliegt."""
    today = (now or datetime.now()).date()
    for path in directory.glob("plot-cut-*.log"):
        stamp = path.stem.removeprefix("plot-cut-")
        try:
            day = datetime.strptime(stamp, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - day).days >= keep_days:
            path.unlink(missing_ok=True)


def append(title: str, detail: str = "", body: str = "") -> None:
    """Haengt einen Eintrag an die Datei von heute und raeumt alte Dateien weg."""
    directory = log_dir()
    purge_old(directory)
    now = datetime.now()
    parts = [f"{now:%Y-%m-%d %H:%M:%S}  {title}"]
    if detail.strip():
        parts.append(detail.strip())
    if body.strip():
        text = body.replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(text) > MAX_BODY:
            text = text[:MAX_BODY] + "\n… (gekürzt, der Rest steht nicht im Protokoll)"
        parts.append(text)
    parts.append("")
    path = directory / f"plot-cut-{now:%Y-%m-%d}.log"
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(parts) + "\n")


def read_text() -> str:
    """Alle noch vorhandenen Tage, der aelteste zuerst."""
    directory = log_dir()
    purge_old(directory)
    files = sorted(directory.glob("plot-cut-*.log"))
    if not files:
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files)


def command_note(payload: str) -> str:
    """Kurzzeile ueber den Befehlsstrom: Anzahl, Kreisbefehl, letzter Befehl."""
    lines = [line for line in payload.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    return (
        f"Befehle: {len(lines)}\n"
        f"Kreisbefehl AA: {'ja' if 'AA' in payload else 'nein'}\n"
        f"Letzter Befehl: {last}"
    )
