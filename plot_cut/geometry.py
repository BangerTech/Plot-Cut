"""Geometrie: Vektordaten (SVG/DXF) in Polylinien (Millimeter) umwandeln,
transformieren, sortieren und fuer das Schneiden aufbereiten.

Konventionen:
- Alle Koordinaten in dieser Datei sind Millimeter.
- y nach oben. SVG liefert y nach unten; beim Import wird gespiegelt.
- ``bottom_left``: Ursprung links unten, X nach rechts (HP-GL / Vevor).
- ``bottom_right``: Ursprung rechts unten, X in die Folie nach links
  (Mimaki / FineCut). Die Form bleibt seitenrichtig.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

Point = tuple[float, float]

MM_PER_PT = 25.4 / 72.0
MM_PER_INCH = 25.4
DEFAULT_FLATNESS_MM = 0.05


@dataclass
class Polyline:
    """Ein zusammenhaengender Linienzug in Millimetern."""

    points: list[Point]
    closed: bool = False
    color: str = "#000000"
    kind: str = "path"  # "path" oder "frame" (Rahmen, nur Kontur)

    def is_empty(self) -> bool:
        return len(self.points) < 2

    def bounds(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def length(self) -> float:
        total = 0.0
        for a, b in zip(self.points, self.points[1:], strict=False):
            total += math.hypot(b[0] - a[0], b[1] - a[1])
        return total

    def signed_area(self) -> float:
        """Doppelte vorzeichenbehaftete Flaeche (Schuhformel).

        Positiv = gegen den Uhrzeigersinn (CCW) in einem y-nach-oben-System.
        """
        pts = self.points
        n = len(pts)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        return area

    def is_ccw(self) -> bool:
        return self.signed_area() > 0.0

    def centroid(self) -> Point:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (sum(xs) / len(xs), sum(ys) / len(ys))


# ---------------------------------------------------------------------------
# Bezier-Abflachung
# ---------------------------------------------------------------------------

def flatten_cubic(
    p0: Point, p1: Point, p2: Point, p3: Point, flatness: float = DEFAULT_FLATNESS_MM
) -> list[Point]:
    """Kubische Bezierkurve adaptiv zu Punkten abflachen (ohne Startpunkt)."""
    out: list[Point] = []

    def recurse(a: Point, b: Point, c: Point, d: Point, depth: int) -> None:
        # Abstand der Kontrollpunkte von der Sehne a-d als Fehlermass.
        d1 = _dist_point_line(b, a, d)
        d2 = _dist_point_line(c, a, d)
        if (d1 + d2) <= flatness or depth > 18:
            out.append(d)
            return
        ab = _mid(a, b)
        bc = _mid(b, c)
        cd = _mid(c, d)
        abc = _mid(ab, bc)
        bcd = _mid(bc, cd)
        abcd = _mid(abc, bcd)
        recurse(a, ab, abc, abcd, depth + 1)
        recurse(abcd, bcd, cd, d, depth + 1)

    recurse(p0, p1, p2, p3, 0)
    return out


def flatten_quadratic(
    p0: Point, p1: Point, p2: Point, flatness: float = DEFAULT_FLATNESS_MM
) -> list[Point]:
    """Quadratische Bezierkurve ueber Grad-Erhoehung zu kubisch abflachen."""
    c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
    c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
    return flatten_cubic(p0, c1, c2, p2, flatness)


def _mid(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _dist_point_line(p: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    seg = math.hypot(dx, dy)
    if seg < 1e-12:
        return math.hypot(px - ax, py - ay)
    return abs((px - ax) * dy - (py - ay) * dx) / seg


# ---------------------------------------------------------------------------
# SVG-Import
# ---------------------------------------------------------------------------

def polylines_from_svg(data: bytes, flatness: float = DEFAULT_FLATNESS_MM) -> list[Polyline]:
    """SVG-Bytes in Polylinien (mm, y nach oben) umwandeln.

    Nutzt ``svgelements`` fuer das volle Pfad- und Transform-Handling und
    faellt auf einen minimalen eigenen Parser zurueck, falls das Paket fehlt.
    """
    try:
        return _polylines_from_svg_svgelements(data, flatness)
    except ImportError:
        return _polylines_from_svg_minimal(data, flatness)


def _polylines_from_svg_svgelements(data: bytes, flatness: float) -> list[Polyline]:
    from svgelements import Close, CubicBezier, Line, Move, Path, QuadraticBezier, SVG

    text = data.decode("utf-8", errors="replace")
    svg = SVG.parse(_io_text(text))

    mm_per_px, height_px, _ = _svg_scale(text)
    polylines: list[Polyline] = []

    for element in svg.elements():
        if not isinstance(element, Path):
            # Rechtecke, Kreise usw. bringt svgelements auch als Path; andere
            # Elemente ohne Geometrie ueberspringen.
            try:
                element = Path(element)  # noqa: PLW2901
            except Exception:
                continue
        if len(element) == 0:
            continue

        color = _stroke_or_fill_color(element)
        current: list[Point] = []
        start: Point | None = None

        for seg in element:
            if isinstance(seg, Move):
                _flush(polylines, current, False, color)
                current = [(_pt(seg.end))]
                start = current[0]
            elif isinstance(seg, Line):
                if not current:
                    current = [_pt(seg.start)]
                current.append(_pt(seg.end))
            elif isinstance(seg, CubicBezier):
                if not current:
                    current = [_pt(seg.start)]
                pts = flatten_cubic(
                    _pt(seg.start), _pt(seg.control1), _pt(seg.control2), _pt(seg.end), flatness
                )
                current.extend(pts)
            elif isinstance(seg, QuadraticBezier):
                if not current:
                    current = [_pt(seg.start)]
                pts = flatten_quadratic(
                    _pt(seg.start), _pt(seg.control), _pt(seg.end), flatness
                )
                current.extend(pts)
            elif isinstance(seg, Close):
                if start is not None and current and current[-1] != start:
                    current.append(start)
                _flush(polylines, current, True, color)
                current = []
                start = None
        _flush(polylines, current, False, color)

    polylines = [_px_polyline_to_mm(pl, height_px, mm_per_px) for pl in polylines]
    return [pl for pl in polylines if not pl.is_empty()]


def _io_text(text: str):
    import io

    return io.StringIO(text)


def _pt(complex_or_point) -> Point:
    # svgelements-Punkte sind komplex-aehnlich mit .x/.y oder (x, y)
    if hasattr(complex_or_point, "x"):
        return (float(complex_or_point.x), float(complex_or_point.y))
    return (float(complex_or_point[0]), float(complex_or_point[1]))


def _stroke_or_fill_color(element) -> str:
    for key in ("stroke", "fill"):
        val = element.values.get(key) if hasattr(element, "values") else None
        if val and str(val).lower() not in ("none", "transparent"):
            return _normalize_color(str(val))
    return "#000000"


def _normalize_color(val: str) -> str:
    val = val.strip()
    if val.startswith("#"):
        if len(val) == 4:  # #abc -> #aabbcc
            return "#" + "".join(c * 2 for c in val[1:]).lower()
        return val[:7].lower()
    return val.lower()


def _px_polyline_to_mm(pl: Polyline, height_px: float, mm_per_px: float) -> Polyline:
    h_mm = height_px * mm_per_px
    pts = [(x * mm_per_px, h_mm - y * mm_per_px) for (x, y) in pl.points]
    return Polyline(points=pts, closed=pl.closed, color=pl.color)


def _has_physical_unit(value: str | None) -> bool:
    """True nur bei mm/cm/in/pt/pc. ``px`` und einheitenlos = VectorCraft-Punkte."""
    if not value:
        return False
    v = value.strip().lower()
    return any(v.endswith(u) for u in ("mm", "cm", "in", "pt", "pc"))


def _svg_scale(text: str, unitless_mm: float = MM_PER_PT) -> tuple[float, float, float]:
    """Liefert (mm pro svgelements-px, Hoehe in svgelements-px, mm pro User-Unit).

    VectorCraft schreibt A4 als ``width="595.276"`` oder ``width="595.276px"`` in
    Punkt. ``px`` darf deshalb nicht als CSS-Pixel (96 dpi) gelesen werden, sonst
    wird aus 30 mm ein 22,5-mm-Schnitt.
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return MM_PER_INCH / 96.0, 0.0, MM_PER_INCH / 96.0

    width = root.get("width")
    height = root.get("height")
    vb = (root.get("viewBox") or "").replace(",", " ").split()
    vb_w = float(vb[2]) if len(vb) == 4 else 0.0
    vb_h = float(vb[3]) if len(vb) == 4 else 0.0

    mm_per_px = MM_PER_INCH / 96.0 if _has_physical_unit(width) else unitless_mm
    width_px = _length_to_px(width) if width else vb_w
    height_px = _length_to_px(height) if height else vb_h
    px_per_user = width_px / vb_w if (vb_w and width_px) else 1.0
    return mm_per_px, height_px, mm_per_px * px_per_user


def _length_to_px(value: str) -> float:
    value = value.strip()
    units = {
        "mm": 96.0 / 25.4,
        "cm": 96.0 / 2.54,
        "in": 96.0,
        "pt": 96.0 / 72.0,
        "pc": 16.0,
        "px": 1.0,
    }
    for suffix, factor in units.items():
        if value.endswith(suffix):
            try:
                return float(value[: -len(suffix)]) * factor
            except ValueError:
                return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _flush(out: list[Polyline], pts: list[Point], closed: bool, color: str) -> None:
    if len(pts) >= 2:
        out.append(Polyline(points=list(pts), closed=closed, color=color))


def _polylines_from_svg_minimal(data: bytes, flatness: float) -> list[Polyline]:
    """Sehr einfacher Rueckfall: liest nur <polyline>, <polygon>, <line>, <rect>.

    Bezierpfade werden hier nicht unterstuetzt; dafuer ist svgelements noetig.
    """
    text = data.decode("utf-8", errors="replace")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    mm_per_px, height_px, mm_per_user = _svg_scale(text)
    height_mm = height_px * mm_per_px
    out: list[Polyline] = []

    def _tag(e) -> str:
        return e.tag.split("}")[-1]

    for el in root.iter():
        tag = _tag(el)
        color = _normalize_color(el.get("stroke") or el.get("fill") or "#000000")
        if tag in ("polyline", "polygon"):
            raw = (el.get("points") or "").replace(",", " ").split()
            nums = [float(x) for x in raw if _is_num(x)]
            pts = [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
            if len(pts) >= 2:
                out.append(Polyline(pts, closed=(tag == "polygon"), color=color))
        elif tag == "line":
            try:
                x1, y1, x2, y2 = (float(el.get(k)) for k in ("x1", "y1", "x2", "y2"))
                out.append(Polyline([(x1, y1), (x2, y2)], color=color))
            except (TypeError, ValueError):
                continue
        elif tag == "rect":
            try:
                x = float(el.get("x", 0))
                y = float(el.get("y", 0))
                w = float(el.get("width"))
                h = float(el.get("height"))
            except (TypeError, ValueError):
                continue
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
            out.append(Polyline(pts, closed=True, color=color))

    def _to_mm(pl: Polyline) -> Polyline:
        pts = [(x * mm_per_user, height_mm - y * mm_per_user) for (x, y) in pl.points]
        return Polyline(pts, closed=pl.closed, color=pl.color)

    return [_to_mm(pl) for pl in out if not pl.is_empty()]


def _is_num(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# DXF-Import (minimal: LINE, LWPOLYLINE, POLYLINE)
# ---------------------------------------------------------------------------

def polylines_from_dxf(data: bytes) -> list[Polyline]:
    """Minimaler DXF-Parser fuer die haeufigsten Schneide-Entities."""
    text = data.decode("utf-8", errors="replace")
    tokens = text.splitlines()
    pairs: list[tuple[str, str]] = []
    it = iter(tokens)
    for code in it:
        try:
            value = next(it)
        except StopIteration:
            break
        pairs.append((code.strip(), value.strip()))

    out: list[Polyline] = []
    i = 0
    n = len(pairs)
    while i < n:
        code, value = pairs[i]
        if code == "0" and value == "LINE":
            x1 = y1 = x2 = y2 = 0.0
            i += 1
            while i < n and pairs[i][0] != "0":
                c, v = pairs[i]
                if c == "10":
                    x1 = float(v)
                elif c == "20":
                    y1 = float(v)
                elif c == "11":
                    x2 = float(v)
                elif c == "21":
                    y2 = float(v)
                i += 1
            out.append(Polyline([(x1, y1), (x2, y2)]))
        elif code == "0" and value in ("LWPOLYLINE", "POLYLINE"):
            pts: list[Point] = []
            closed = False
            cur_x: float | None = None
            i += 1
            while i < n and not (pairs[i][0] == "0" and pairs[i][1] in ("SEQEND", "LINE",
                                 "LWPOLYLINE", "POLYLINE", "ENDSEC", "VERTEX") and value != "POLYLINE"):
                c, v = pairs[i]
                if c == "0" and v == "SEQEND":
                    i += 1
                    break
                if c == "70":
                    closed = bool(int(float(v)) & 1)
                elif c == "10":
                    cur_x = float(v)
                elif c == "20" and cur_x is not None:
                    pts.append((cur_x, float(v)))
                    cur_x = None
                elif c == "0" and v == "VERTEX":
                    pass
                i += 1
            if len(pts) >= 2:
                out.append(Polyline(pts, closed=closed))
        else:
            i += 1
    return [pl for pl in out if not pl.is_empty()]


def polylines_from_bytes(
    data: bytes, fmt: str, flatness: float = DEFAULT_FLATNESS_MM
) -> list[Polyline]:
    if fmt == "svg":
        return polylines_from_svg(data, flatness)
    if fmt == "dxf":
        return polylines_from_dxf(data)
    raise ValueError(f"Unbekanntes Format: {fmt}")


# ---------------------------------------------------------------------------
# Transformationen
# ---------------------------------------------------------------------------

def scale(
    polylines: list[Polyline], sx: float, sy: float, about: Point | None = None
) -> list[Polyline]:
    """Skaliert um ``about`` (Default: Ursprung)."""
    ox, oy = about or (0.0, 0.0)
    return [
        Polyline(
            [((x - ox) * sx + ox, (y - oy) * sy + oy) for (x, y) in pl.points],
            pl.closed,
            pl.color,
            pl.kind,
        )
        for pl in polylines
    ]


def translate(polylines: list[Polyline], dx: float, dy: float) -> list[Polyline]:
    return [
        Polyline([(x + dx, y + dy) for (x, y) in pl.points], pl.closed, pl.color, pl.kind)
        for pl in polylines
    ]


def rotate(polylines: list[Polyline], degrees: float, about: Point | None = None) -> list[Polyline]:
    rad = math.radians(degrees)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    if about is None:
        about = (0.0, 0.0)
    ox, oy = about
    out: list[Polyline] = []
    for pl in polylines:
        pts = []
        for x, y in pl.points:
            tx, ty = x - ox, y - oy
            pts.append((ox + tx * cos_a - ty * sin_a, oy + tx * sin_a + ty * cos_a))
        out.append(Polyline(pts, pl.closed, pl.color, pl.kind))
    return out


def mirror_x(polylines: list[Polyline], axis_x: float | None = None) -> list[Polyline]:
    """Horizontal spiegeln um die senkrechte Achse ``axis_x`` (Default: Bbox-Mitte)."""
    if axis_x is None:
        minx, _, maxx, _ = bounds_of(polylines)
        axis_x = (minx + maxx) / 2.0
    return [
        Polyline([(2 * axis_x - x, y) for (x, y) in pl.points], pl.closed, pl.color, pl.kind)
        for pl in polylines
    ]


def move_to_origin(polylines: list[Polyline], margin: float = 0.0) -> list[Polyline]:
    """Verschiebt so, dass die Bounding-Box bei (margin, margin) beginnt."""
    minx, miny, _, _ = bounds_of(polylines)
    return translate(polylines, -minx + margin, -miny + margin)


def align_to_origin(
    polylines: list[Polyline], *, corner: str = "bottom_left", margin: float = 0.0
) -> list[Polyline]:
    """Legt die Bounding-Box an den Plotter-Ursprung.

    ``bottom_left``: linke untere Ecke bei (margin, margin), X nach rechts.
    ``bottom_right``: rechte untere Ecke am Ursprung (Mimaki/FineCut). Maschinen-X
    ist der Abstand von dieser Kante und waechst in die Folie hinein. Die Form
    bleibt seitenrichtig, wenn die Vorschau +X nach links zeichnet.
    """
    work = move_to_origin(polylines, margin=margin)
    if corner != "bottom_right" or not work:
        return work
    _, _, maxx, _ = bounds_of(work)
    return [
        Polyline([(maxx - x, y) for (x, y) in pl.points], pl.closed, pl.color, pl.kind) for pl in work
    ]


def bounds_of(polylines: list[Polyline]) -> tuple[float, float, float, float]:
    if not polylines:
        return (0.0, 0.0, 0.0, 0.0)
    minx = miny = math.inf
    maxx = maxy = -math.inf
    for pl in polylines:
        bx0, by0, bx1, by1 = pl.bounds()
        minx = min(minx, bx0)
        miny = min(miny, by0)
        maxx = max(maxx, bx1)
        maxy = max(maxy, by1)
    return (minx, miny, maxx, maxy)


# ---------------------------------------------------------------------------
# Overcut und Schneidrichtung
# ---------------------------------------------------------------------------

def apply_overcut(pl: Polyline, overcut_mm: float) -> Polyline:
    """Verlaengert geschlossene Pfade um ``overcut_mm`` ueber den Startpunkt."""
    if overcut_mm <= 0 or not pl.closed or len(pl.points) < 3:
        return pl
    pts = list(pl.points)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    remaining = overcut_mm
    out = list(pts)
    for a, b in zip(pts, pts[1:], strict=False):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if seg <= 1e-9:
            continue
        if seg >= remaining:
            t = remaining / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            break
        out.append(b)
        remaining -= seg
    return Polyline(out, closed=pl.closed, color=pl.color, kind=pl.kind)


def ensure_direction(pl: Polyline, ccw: bool) -> Polyline:
    """Dreht die Punktreihenfolge, falls die Richtung nicht passt."""
    if not pl.closed or len(pl.points) < 3:
        return pl
    if pl.is_ccw() != ccw:
        return Polyline(list(reversed(pl.points)), closed=pl.closed, color=pl.color, kind=pl.kind)
    return pl


# ---------------------------------------------------------------------------
# Sortierung der Schneidreihenfolge
# ---------------------------------------------------------------------------

def _contains(outer: Polyline, inner: Polyline) -> bool:
    """Grobe Enthaltenseins-Pruefung ueber die Bounding-Box.

    Fuer die Schneidreihenfolge reicht es, ineinander geschachtelte Pfade zu
    erkennen. Die Bounding-Box ist dabei robuster als ein Schwerpunkt-Test:
    konzentrische Formen (gleicher Mittelpunkt) wuerden sich sonst gegenseitig
    als "enthalten" melden.
    """
    if not outer.closed or len(outer.points) < 3:
        return False
    ox0, oy0, ox1, oy1 = outer.bounds()
    ix0, iy0, ix1, iy1 = inner.bounds()
    eps = 1e-6
    strictly_inside = (
        ox0 <= ix0 + eps
        and oy0 <= iy0 + eps
        and ox1 >= ix1 - eps
        and oy1 >= iy1 - eps
    )
    if not strictly_inside:
        return False
    # Gleich grosse Boxen gelten nicht als Verschachtelung.
    outer_area = (ox1 - ox0) * (oy1 - oy0)
    inner_area = (ix1 - ix0) * (iy1 - iy0)
    return outer_area > inner_area + eps


def sort_cut_order(
    polylines: list[Polyline], inner_first: bool = True, minimize_travel: bool = True
) -> list[Polyline]:
    """Ordnet Pfade: optional innen vor aussen, dann kuerzeste Leerfahrt (greedy)."""
    items = list(polylines)
    if not items:
        return []

    levels: list[list[Polyline]] = [items]
    if inner_first:
        depth: list[int] = []
        for i, inner in enumerate(items):
            d = 0
            for j, outer in enumerate(items):
                if i != j and _contains(outer, inner):
                    d += 1
            depth.append(d)
        # groessere Tiefe (weiter innen) zuerst -- stabil nach Ausgangsindex
        levels = [
            [items[k] for k in range(len(items)) if depth[k] == d]
            for d in sorted(set(depth), reverse=True)
        ]

    if not minimize_travel:
        return [pl for level in levels for pl in level]

    # Greedy-Nearest-Neighbour ab (0,0), nur innerhalb einer Tiefe: sonst wuerde
    # ein Aussenpfad vor seinen Innenpfaden geschnitten.
    result: list[Polyline] = []
    cursor: Point = (0.0, 0.0)
    for level in levels:
        remaining = level[:]
        while remaining:
            best_idx = 0
            best_dist = math.inf
            for idx, pl in enumerate(remaining):
                start = pl.points[0]
                dist = math.hypot(start[0] - cursor[0], start[1] - cursor[1])
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
            chosen = remaining.pop(best_idx)
            result.append(chosen)
            cursor = chosen.points[-1]
    return result


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

@dataclass
class CutJob:
    """Fertig aufbereiteter Schneidauftrag in Millimetern."""

    polylines: list[Polyline] = field(default_factory=list)
    width_mm: float = 0.0
    height_mm: float = 0.0

    @property
    def total_cut_mm(self) -> float:
        return sum(pl.length() for pl in self.polylines)


def prepare_job(
    polylines: list[Polyline],
    *,
    rotate_deg: float = 0.0,
    mirror: bool = False,
    overcut_mm: float = 0.0,
    sort: bool = True,
    inner_first: bool = True,
    margin_mm: float = 0.0,
    origin: str = "bottom_left",
) -> CutJob:
    """Wendet Transformationen, Sortierung, Richtung und Overcut der Reihe nach an."""
    work = polylines
    if rotate_deg:
        work = rotate(work, rotate_deg)
    if mirror:
        work = mirror_x(work)
    # "keep": Pfade sind schon platziert (Offset, Kopien). Nicht erneut an 0 schieben.
    if origin != "keep":
        work = align_to_origin(work, corner=origin, margin=margin_mm)

    if sort:
        work = sort_cut_order(work, inner_first=inner_first, minimize_travel=True)

    # Geschlossene Pfade gegen den Uhrzeigersinn (FineCut-Konvention: schwarz/CCW),
    # danach Overcut anhaengen.
    finished: list[Polyline] = []
    for pl in work:
        pl = ensure_direction(pl, ccw=True)
        pl = apply_overcut(pl, overcut_mm)
        finished.append(pl)

    minx, miny, maxx, maxy = bounds_of(finished)
    return CutJob(polylines=finished, width_mm=maxx - minx, height_mm=maxy - miny)
