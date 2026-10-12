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
    kind: str = "path"  # "path" (gefuellt), "line" (fill="none") oder "frame" (Rahmen)
    group: int = 0  # Teilpfade eines SVG-Pfads (z. B. Loch im P) teilen sich die Gruppe

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
    group = 0

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

        group += 1
        color = _stroke_or_fill_color(element)
        kind = "path" if _is_filled(element) else "line"
        current: list[Point] = []
        start: Point | None = None

        for seg in element:
            if isinstance(seg, Move):
                _flush(polylines, current, False, color, kind, group)
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
                _flush(polylines, current, True, color, kind, group)
                current = []
                start = None
        _flush(polylines, current, False, color, kind, group)

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


def _is_filled(element) -> bool:
    """SVG fuellt ohne ``fill``-Angabe schwarz; nur ``fill="none"`` ist reine Linie."""
    val = element.values.get("fill") if hasattr(element, "values") else None
    return not (val and str(val).lower() in ("none", "transparent"))


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
    return _carry(pl, pts)


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


def _flush(
    out: list[Polyline],
    pts: list[Point],
    closed: bool,
    color: str,
    kind: str = "path",
    group: int = 0,
) -> None:
    if len(pts) >= 2:
        out.append(Polyline(points=list(pts), closed=closed, color=color, kind=kind, group=group))


def _carry(pl: Polyline, points: list[Point], closed: bool | None = None) -> Polyline:
    """Neue Punkte, gleiche Farbe, Art und Gruppe (Loch bleibt beim Buchstaben)."""
    return Polyline(
        points=points,
        closed=pl.closed if closed is None else closed,
        color=pl.color,
        kind=pl.kind,
        group=pl.group,
    )


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
        fill = (el.get("fill") or "").strip().lower()
        kind = "line" if fill in ("none", "transparent") else "path"
        color = _normalize_color(el.get("stroke") or el.get("fill") or "#000000")
        group = len(out) + 1
        if tag in ("polyline", "polygon"):
            raw = (el.get("points") or "").replace(",", " ").split()
            nums = [float(x) for x in raw if _is_num(x)]
            pts = [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
            if len(pts) >= 2:
                out.append(Polyline(pts, closed=(tag == "polygon"), color=color, kind=kind, group=group))
        elif tag == "line":
            try:
                x1, y1, x2, y2 = (float(el.get(k)) for k in ("x1", "y1", "x2", "y2"))
                out.append(Polyline([(x1, y1), (x2, y2)], color=color, kind=kind, group=group))
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
            out.append(Polyline(pts, closed=True, color=color, kind=kind, group=group))

    def _to_mm(pl: Polyline) -> Polyline:
        pts = [(x * mm_per_user, height_mm - y * mm_per_user) for (x, y) in pl.points]
        return _carry(pl, pts)

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
            out.append(Polyline([(x1, y1), (x2, y2)], group=len(out) + 1))
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
                out.append(Polyline(pts, closed=closed, group=len(out) + 1))
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
        _carry(pl, [((x - ox) * sx + ox, (y - oy) * sy + oy) for (x, y) in pl.points])
        for pl in polylines
    ]


def translate(polylines: list[Polyline], dx: float, dy: float) -> list[Polyline]:
    return [
        _carry(pl, [(x + dx, y + dy) for (x, y) in pl.points])
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
        out.append(_carry(pl, pts))
    return out


def mirror_x(polylines: list[Polyline], axis_x: float | None = None) -> list[Polyline]:
    """Horizontal spiegeln um die senkrechte Achse ``axis_x`` (Default: Bbox-Mitte)."""
    if axis_x is None:
        minx, _, maxx, _ = bounds_of(polylines)
        axis_x = (minx + maxx) / 2.0
    return [
        _carry(pl, [(2 * axis_x - x, y) for (x, y) in pl.points])
        for pl in polylines
    ]


def mirror_y(polylines: list[Polyline], axis_y: float | None = None) -> list[Polyline]:
    """Vertikal spiegeln um die waagerechte Achse ``axis_y`` (Default: Bbox-Mitte)."""
    if axis_y is None:
        _, miny, _, maxy = bounds_of(polylines)
        axis_y = (miny + maxy) / 2.0
    return [
        _carry(pl, [(x, 2 * axis_y - y) for (x, y) in pl.points])
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
        _carry(pl, [(maxx - x, y) for (x, y) in pl.points]) for pl in work
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


def split_outer_and_holes(parts: list[tuple[int, dict]]) -> tuple[list[int], list[int]]:
    """Teilt Offset-Pfade in Aussenkontur und Loecher.

    Ein Teil ist ein Loch, wenn seine Box komplett in einer groesseren liegt.
    Getrennte Buchstaben behalten dadurch jeder seine Aussenlinie.
    ``parts`` ist ``(id, bounds)`` mit ``x``, ``y``, ``width``, ``height``.
    """
    keep: list[int] = []
    holes: list[int] = []
    for pid, bounds in parts:
        if any(_bounds_inside(bounds, other) for oid, other in parts if oid != pid):
            holes.append(pid)
        else:
            keep.append(pid)
    return keep, holes


def _bounds_inside(inner: dict, outer: dict, eps: float = 0.4) -> bool:
    try:
        ix, iy = float(inner["x"]), float(inner["y"])
        iw, ih = float(inner["width"]), float(inner["height"])
        ox, oy = float(outer["x"]), float(outer["y"])
        ow, oh = float(outer["width"]), float(outer["height"])
    except (KeyError, TypeError, ValueError):
        return False
    if iw <= 0 or ih <= 0 or ow <= 0 or oh <= 0:
        return False
    if iw * ih >= ow * oh * 0.98:
        return False
    return (
        ix >= ox - eps
        and iy >= oy - eps
        and ix + iw <= ox + ow + eps
        and iy + ih <= oy + oh + eps
    )


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
    return _carry(pl, out)


def ensure_direction(pl: Polyline, ccw: bool) -> Polyline:
    """Dreht die Punktreihenfolge, falls die Richtung nicht passt."""
    if not pl.closed or len(pl.points) < 3:
        return pl
    if pl.is_ccw() != ccw:
        return _carry(pl, list(reversed(pl.points)))
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


def _clip_segment(
    x0: float, y0: float, x1: float, y1: float, rect: tuple[float, float, float, float]
) -> tuple[float, float, float, float] | None:
    xmin, ymin, xmax, ymax = rect
    dx, dy = x1 - x0, y1 - y0
    p = (-dx, dx, -dy, dy)
    q = (x0 - xmin, xmax - x0, y0 - ymin, ymax - y0)
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q, strict=False):
        if abs(pi) < 1e-12:
            if qi < 0:
                return None
            continue
        t = qi / pi
        if pi < 0:
            u1 = max(u1, t)
        else:
            u2 = min(u2, t)
        if u1 > u2:
            return None
    return (x0 + u1 * dx, y0 + u1 * dy, x0 + u2 * dx, y0 + u2 * dy)


def clip_to_rect(
    polylines: list[Polyline], x0: float, y0: float, x1: float, y1: float
) -> list[Polyline]:
    """Schneidet Pfade auf das Rechteck. Geschlossene Pfade koennen aufgehen."""
    rect = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    out: list[Polyline] = []
    for pl in polylines:
        current: list[Point] = []
        pts = pl.points
        for a, b in zip(pts, pts[1:], strict=False):
            clipped = _clip_segment(a[0], a[1], b[0], b[1], rect)
            if clipped is None:
                if len(current) >= 2:
                    out.append(_carry(pl, list(current), closed=False))
                current = []
                continue
            cx0, cy0, cx1, cy1 = clipped
            if not current:
                current.append((cx0, cy0))
            elif math.hypot(current[-1][0] - cx0, current[-1][1] - cy0) > 1e-6:
                if len(current) >= 2:
                    out.append(_carry(pl, list(current), closed=False))
                current = [(cx0, cy0)]
            current.append((cx1, cy1))
        if len(current) >= 2:
            closed = bool(pl.closed and current[0] == current[-1])
            out.append(_carry(pl, list(current), closed=closed))
    return [pl for pl in out if not pl.is_empty()]


def tile_sheets(
    polylines: list[Polyline],
    sheet_w: float,
    sheet_h: float,
    overlap: float = 0.0,
) -> list[tuple[int, int, list[Polyline]]]:
    """Teilt das Motiv in Folienkacheln. Koordinaten je Kachel am Ursprung."""
    if not polylines:
        return []
    minx, miny, maxx, maxy = bounds_of(polylines)
    usable_w = max(sheet_w - max(overlap, 0.0), 1.0)
    usable_h = max(sheet_h - max(overlap, 0.0), 1.0)
    nx = max(1, math.ceil((maxx - minx) / usable_w - 1e-9))
    ny = max(1, math.ceil((maxy - miny) / usable_h - 1e-9))
    tiles: list[tuple[int, int, list[Polyline]]] = []
    for iy in range(ny):
        for ix in range(nx):
            x0 = minx + ix * usable_w
            y0 = miny + iy * usable_h
            clipped = clip_to_rect(polylines, x0, y0, x0 + sheet_w, y0 + sheet_h)
            if not clipped:
                continue
            tiles.append((ix, iy, translate(clipped, -x0, -y0)))
    return tiles


def circle_arc(pl: Polyline) -> tuple[float, float, bool, list[Point]] | None:
    """Voller Kreis: Mittelpunkt, Drehsinn und Overcut-Rest hinter dem Schliessen.

    Die Punkte muessen auf einem Kreis liegen und der Umfang dicht genug sein,
    damit ein Achteck ein Achteck bleibt. Teilboegen liefert diese Funktion nicht.
    """
    if not pl.closed or len(pl.points) < 24:
        return None
    pts = pl.points
    start = pts[0]
    close_at: int | None = None
    for i in range(8, len(pts)):
        if math.hypot(pts[i][0] - start[0], pts[i][1] - start[1]) <= 0.05:
            close_at = i
            break
    loop = pts[: close_at + 1] if close_at is not None else pts
    if len(loop) < 24:
        return None
    sample = loop[:-1] if math.hypot(loop[-1][0] - start[0], loop[-1][1] - start[1]) <= 0.05 else loop
    if len(sample) < 24:
        return None
    cx = sum(p[0] for p in sample) / len(sample)
    cy = sum(p[1] for p in sample) / len(sample)
    radii = [math.hypot(p[0] - cx, p[1] - cy) for p in sample]
    radius = sum(radii) / len(radii)
    if radius < 0.3:
        return None
    if max(abs(d - radius) for d in radii) > max(0.08, radius * 0.02):
        return None
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(loop, loop[1:], strict=False))
    if length < 0.995 * 2.0 * math.pi * radius:
        return None
    area = 0.0
    ring = sample
    for i, (x1, y1) in enumerate(ring):
        x2, y2 = ring[(i + 1) % len(ring)]
        area += x1 * y2 - x2 * y1
    tail = list(pts[close_at + 1 :]) if close_at is not None else []
    while tail and math.hypot(tail[0][0] - start[0], tail[0][1] - start[1]) <= 0.05:
        tail.pop(0)
    return cx, cy, area > 0.0, tail


def circle_polyline(
    cx: float, cy: float, radius: float, *, n: int = 36, color: str = "#111111"
) -> Polyline:
    pts = [
        (cx + radius * math.cos(2 * math.pi * i / n), cy + radius * math.sin(2 * math.pi * i / n))
        for i in range(n + 1)
    ]
    return Polyline(pts, closed=True, color=color, kind="path")


def _square_mark(cx: float, cy: float, size: float, color: str) -> Polyline:
    h = size / 2.0
    pts = [
        (cx - h, cy - h),
        (cx + h, cy - h),
        (cx + h, cy + h),
        (cx - h, cy + h),
        (cx - h, cy - h),
    ]
    return Polyline(pts, closed=True, color=color, kind="path")


def registration_marks(
    polylines: list[Polyline],
    *,
    placement: str = "outer",
    size_mm: float = 10.0,
    round_fill: bool = False,
    extra: bool = False,
    color: str = "#be1b22",
) -> list[Polyline]:
    """Passermarken an den Ecken der Bounding-Box, aussen oder innen."""
    if not polylines:
        return []
    minx, miny, maxx, maxy = bounds_of(polylines)
    size = max(size_mm, 1.0)
    inset = size / 2.0
    if placement == "inner":
        xs = (minx + inset, maxx - inset)
        ys = (miny + inset, maxy - inset)
    else:
        xs = (minx - inset, maxx + inset)
        ys = (miny - inset, maxy + inset)
    corners = [(xs[0], ys[0]), (xs[1], ys[0]), (xs[0], ys[1]), (xs[1], ys[1])]
    marks = [
        circle_polyline(x, y, size / 2.0, color=color) if round_fill else _square_mark(x, y, size, color)
        for x, y in corners
    ]
    if extra:
        mx = (xs[0] + xs[1]) / 2.0
        my = ys[1]
        marks.append(
            circle_polyline(mx, my, size / 2.0, color=color)
            if round_fill
            else _square_mark(mx, my, size, color)
        )
    return marks


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
