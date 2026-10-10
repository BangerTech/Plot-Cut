"""Erzeugt Plotterbefehle (MGL-IIc bzw. HP-GL) aus einem CutJob.

MGL-IIc ist Mimakis HP-GL-Dialekt. Fuer reines Schneiden reichen wenige Befehle:

- ``IN;``            Initialisieren / Ursprung setzen
- ``PU x,y;``        Pen Up (Leerfahrt) zu Koordinate
- ``PD x,y,...;``    Pen Down (schneiden), beliebig viele Punkte
- ``VSn;``           Geschwindigkeit in cm/s
- ``FSn;`` / ``!FSn;`` Klingendruck in g (modellabhaengig; hier ``FS``)
- ``!PT d;``         Klingenoffset (mm, modellabhaengig)
- ``PU;`` am Ende    Kopf anheben

Koordinaten werden in Plotterschritten ausgegeben (1 Schritt = 0,025 mm).
"""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import CutJob, Polyline

STEPS_PER_MM = 40.0  # 1 / 0.025 mm


@dataclass
class CutCondition:
    """Schneidbedingung fuer eine Farbe/Ebene."""

    tool: int = 1
    speed: int = 30  # cm/s
    pressure: int = 100  # g
    offset: float = 0.3  # mm
    enabled: bool = True


@dataclass
class PlotOptions:
    language: str = "mgl2"  # "mgl2" | "hpgl"
    origin_bottom_left: bool = True
    emit_conditions: bool = True


def mm_to_steps(value_mm: float) -> int:
    return int(round(value_mm * STEPS_PER_MM))


def _coord(x_mm: float, y_mm: float) -> str:
    return f"{mm_to_steps(x_mm)},{mm_to_steps(y_mm)}"


def _condition_commands(cond: CutCondition, language: str) -> list[str]:
    cmds: list[str] = []
    # Werkzeugwahl ist modellabhaengig; bei MGL ueblich mit ``!FW`` oder Logical
    # Pen ``SPn``. Wir nutzen SP fuer breite Kompatibilitaet.
    cmds.append(f"SP{cond.tool};")
    cmds.append(f"VS{cond.speed};")
    cmds.append(f"FS{cond.pressure};")
    if language == "mgl2":
        # Klingenoffset in mm, als Hundertstel mm ueblich. Wir geben mm*100.
        cmds.append(f"!PT{int(round(cond.offset * 100))};")
    return cmds


def generate(
    job: CutJob,
    *,
    conditions_by_color: dict[str, CutCondition] | None = None,
    default_condition: CutCondition | None = None,
    options: PlotOptions | None = None,
    copies: int = 1,
) -> str:
    """Baut den vollstaendigen Befehlsstrom als Text."""
    options = options or PlotOptions()
    default_condition = default_condition or CutCondition()
    conditions_by_color = conditions_by_color or {}

    lines: list[str] = ["IN;"]

    # Pfade nach Farbe gruppieren, Reihenfolge der ersten Vorkommen beibehalten.
    groups: list[tuple[str, list[Polyline]]] = []
    index: dict[str, int] = {}
    for pl in job.polylines:
        if pl.color not in index:
            index[pl.color] = len(groups)
            groups.append((pl.color, []))
        groups[index[pl.color]][1].append(pl)

    for _copy in range(max(1, copies)):
        for color, pls in groups:
            cond = conditions_by_color.get(color, default_condition)
            if not cond.enabled:
                continue
            if options.emit_conditions:
                lines.extend(_condition_commands(cond, options.language))
            for pl in pls:
                lines.extend(_polyline_commands(pl))

    lines.append("PU0,0;")
    return "\n".join(lines) + "\n"


def _polyline_commands(pl: Polyline) -> list[str]:
    if pl.is_empty():
        return []
    pts = pl.points
    cmds = [f"PU{_coord(*pts[0])};"]
    rest = ",".join(_coord(x, y) for (x, y) in pts[1:])
    if rest:
        cmds.append(f"PD{rest};")
    return cmds


def generate_bytes(job: CutJob, **kwargs) -> bytes:
    return generate(job, **kwargs).encode("ascii", errors="replace")
