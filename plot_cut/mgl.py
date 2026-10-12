"""Erzeugt Plotterbefehle (MGL-IIc, HP-GL, DMPL) aus einem CutJob.

MGL-IIc ist Mimakis HP-GL-Dialekt. Die Formate stammen aus FineCut und XFCut:

- ``mgl2``: Start ``IN;IP0,0,1,1;``, ``PU``/``PD``, ``SP``, ``VS``, ``FS``, Offset ``ZO``.
  0,025 mm als Ganzzahl-Schritte, 0,01 mm als ``PU%.2f,%.2f;``.
  Volle Kreise als ``AA`` Mittelpunkt und 360 Grad.
- ``hpgl``: Start ``IN;PA;``, Ganzzahl-Schritte, Ende optional ``PG;``, Kreise als ``AA``.
- ``dmpl``: Kopf ``;:H A L0 ECN U ``, Fahrt ``U``, Schnitt ``D``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import CutJob, Polyline, bounds_of

TOOLS = [
    ("CT1", 1),
    ("PEN", 2),
    ("CT2", 3),
    ("CT3", 4),
    ("PIN", 5),
    ("HLF", 6),
    ("CT4", 7),
    ("CT5", 8),
]

STEP_CHOICES_MGL = [(0.025, "0.025 mm"), (0.01, "0.01 mm")]
STEP_CHOICES_GENERIC = [
    (0.10, "0.10 mm"),
    (0.05, "0.05 mm"),
    (0.025, "0.025 mm"),
    (0.010, "0.010 mm"),
]


def speed_range(language: str) -> tuple[int, int]:
    return (1, 120) if language == "mgl2" else (1, 100)


def pressure_range(language: str) -> tuple[int, int]:
    return (1, 500) if language == "mgl2" else (10, 500)


def step_choices(language: str) -> list[tuple[float, str]]:
    return STEP_CHOICES_MGL if language == "mgl2" else STEP_CHOICES_GENERIC


def default_step_mm(language: str) -> float:
    return 0.025


@dataclass
class CutCondition:
    """Schneidbedingung fuer eine Farbe/Ebene."""

    tool: int = 1
    speed: int | None = 30  # cm/s, None = Wert am Plotter lassen
    pressure: int | None = 100  # g
    offset: float | None = 0.3  # mm
    enabled: bool = True


@dataclass
class PlotOptions:
    language: str = "mgl2"  # "mgl2" | "hpgl" | "dmpl"
    emit_conditions: bool = True
    group_by_color: bool = True
    park_mm: tuple[float, float] | None = None
    step_mm: float = 0.025
    end_action: str = "origin"  # "origin" | "feed" | "stay"
    feed_mm: float = 20.0
    extra_passes: int = 0  # zusaetzliche Wiederholungen jedes Pfads


def steps_per_mm(step_mm: float) -> float:
    return 1.0 / max(step_mm, 1e-9)


def mm_to_steps(value_mm: float, step_mm: float = 0.025) -> int:
    return int(round(value_mm * steps_per_mm(step_mm)))


class _Emitter:
    def __init__(self, language: str, step_mm: float) -> None:
        self.language = language
        self.step_mm = step_mm
        self.mgl_float = language == "mgl2" and abs(step_mm - 0.01) < 1e-9
        # Beim Mimaki ist die erste Koordinate der Vorschub (lange Achse), die
        # zweite der Schlitten (Folienbreite). Die Design-Horizontale muss auf die
        # Breite, sonst stehen nebeneinander angeordnete Formen uebereinander.
        self.swap_xy = language == "mgl2"

    def coord(self, x_mm: float, y_mm: float) -> str:
        if self.swap_xy:
            x_mm, y_mm = y_mm, x_mm
        if self.mgl_float:
            return f"{x_mm:.2f},{y_mm:.2f}"
        return f"{mm_to_steps(x_mm, self.step_mm)},{mm_to_steps(y_mm, self.step_mm)}"

    def start(self) -> list[str]:
        if self.language == "dmpl":
            return [";:H A L0 ECN U "]
        if self.language == "hpgl":
            return ["IN;PA;"]
        return ["IN;IP0,0,1,1;"]

    def move(self, x_mm: float, y_mm: float) -> str:
        c = self.coord(x_mm, y_mm)
        if self.language == "dmpl":
            return f"U{c}"
        return f"PU{c};"

    def full_circle(self, cx_mm: float, cy_mm: float, ccw: bool) -> str | None:
        """HP-GL ``AA`` fuer einen vollen Kreis. DMPL hat diesen Befehl nicht."""
        if self.language == "dmpl":
            return None
        angle = 360.0 if ccw else -360.0
        ang = f"{angle:.2f}" if self.mgl_float else f"{int(angle)}"
        return f"AA{self.coord(cx_mm, cy_mm)},{ang};"

    def cut(self, points: list[tuple[float, float]]) -> list[str]:
        if not points:
            return []
        if self.language == "dmpl":
            return [f"D{self.coord(x, y)}" for x, y in points]
        # Ein Koordinatenpaar pro PD, wie FineCut (PD%.2lf,%.2lf; in MmkCutCtrl.dll).
        # Ein PD mit vielen Paaren liess der CG-60SR aus (Kreis ungeschnitten),
        # das kurze Rechteck lief noch. Der Kopf bleibt unten, jedes PD schneidet weiter.
        return [f"PD{self.coord(x, y)};" for x, y in points]

    def origin(self) -> list[str]:
        cmds = [self.move(0.0, 0.0)]
        if self.language == "hpgl":
            cmds.append("PG;")
        return cmds


def _condition_commands(cond: CutCondition, language: str) -> list[str]:
    cmds: list[str] = []
    if language == "dmpl":
        return cmds
    cmds.append(f"SP{cond.tool};")
    if cond.speed is not None:
        cmds.append(f"VS{cond.speed};")
    if cond.pressure is not None:
        cmds.append(f"FS{cond.pressure};")
    if language == "mgl2" and cond.offset is not None:
        cmds.append(f"ZO{cond.offset:.1f};")
    return cmds


def _group_polylines(
    job: CutJob,
    conditions_by_color: dict[str, CutCondition],
    default_condition: CutCondition,
    group_by_color: bool,
) -> list[tuple[CutCondition, list[Polyline]]]:
    groups: list[tuple[CutCondition, list[Polyline]]] = []
    index: dict[str, int] = {}
    for pl in job.polylines:
        cond = conditions_by_color.get(pl.color, default_condition)
        if not cond.enabled:
            continue
        if group_by_color:
            if pl.color not in index:
                index[pl.color] = len(groups)
                groups.append((cond, []))
            groups[index[pl.color]][1].append(pl)
        elif groups and groups[-1][0] == cond:
            groups[-1][1].append(pl)
        else:
            groups.append((cond, [pl]))
    return groups


def _polyline_commands(pl: Polyline, emit: _Emitter, extra_passes: int) -> list[str]:
    if pl.is_empty():
        return []
    # Volle Kreise bleiben Linien (ein PD je Punkt). AA hat der CG-60SR beim
    # Schneiden ausgelassen; full_circle bleibt im Code, bis das Format belegt ist.
    pts = pl.points
    cmds = [emit.move(*pts[0])]
    cmds.extend(emit.cut(pts[1:]))
    for _ in range(max(0, extra_passes)):
        cmds.append(emit.move(*pts[0]))
        cmds.extend(emit.cut(pts[1:]))
    return cmds


def _finish(lines: list[str], job: CutJob, options: PlotOptions, emit: _Emitter) -> None:
    if options.park_mm is not None:
        lines.append(emit.move(*options.park_mm))
    if options.end_action == "origin":
        lines.extend(emit.origin())
    elif options.end_action == "feed":
        maxy = 0.0
        if job.polylines:
            _minx, _miny, _maxx, maxy = bounds_of(job.polylines)
        lines.append(emit.move(0.0, maxy + options.feed_mm))


def generate(
    job: CutJob,
    *,
    conditions_by_color: dict[str, CutCondition] | None = None,
    default_condition: CutCondition | None = None,
    options: PlotOptions | None = None,
    copies: int = 1,
) -> str:
    """Baut den vollstaendigen Befehlsstrom als Text."""
    chunks = generate_chunks(
        job,
        conditions_by_color=conditions_by_color,
        default_condition=default_condition,
        options=options,
        copies=copies,
        split_colors=False,
    )
    return chunks[0] if chunks else ""


def generate_chunks(
    job: CutJob,
    *,
    conditions_by_color: dict[str, CutCondition] | None = None,
    default_condition: CutCondition | None = None,
    options: PlotOptions | None = None,
    copies: int = 1,
    split_colors: bool = False,
) -> list[str]:
    """Ein Text je Farbe, wenn ``split_colors``, sonst ein Block."""
    options = options or PlotOptions()
    default_condition = default_condition or CutCondition()
    conditions_by_color = conditions_by_color or {}
    emit = _Emitter(options.language, options.step_mm)
    groups = _group_polylines(job, conditions_by_color, default_condition, options.group_by_color)
    if not groups:
        return ["\n".join(emit.start()) + "\n"]

    def emit_groups(selected: list[tuple[CutCondition, list[Polyline]]], with_start: bool, with_end: bool) -> str:
        lines: list[str] = emit.start() if with_start else []
        for _copy in range(max(1, copies)):
            for cond, pls in selected:
                if options.emit_conditions:
                    lines.extend(_condition_commands(cond, options.language))
                for pl in pls:
                    lines.extend(_polyline_commands(pl, emit, options.extra_passes))
        if with_end:
            pls = [pl for _c, group in selected for pl in group]
            part = CutJob(polylines=pls) if pls else job
            _finish(lines, part, options, emit)
        return "\n".join(lines) + "\n"

    if split_colors and len(groups) > 1:
        out: list[str] = []
        for i, group in enumerate(groups):
            out.append(emit_groups([group], with_start=i == 0, with_end=i == len(groups) - 1))
        return out
    return [emit_groups(groups, with_start=True, with_end=True)]


def generate_bytes(job: CutJob, **kwargs) -> bytes:
    return generate(job, **kwargs).encode("ascii", errors="replace")


def generate_chunk_bytes(
    job: CutJob,
    *,
    split_colors: bool = False,
    **kwargs,
) -> list[bytes]:
    return [
        text.encode("ascii", errors="replace")
        for text in generate_chunks(job, split_colors=split_colors, **kwargs)
    ]
