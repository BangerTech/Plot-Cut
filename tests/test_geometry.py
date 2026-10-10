"""Tests fuer die Geometrie-Pipeline."""

from __future__ import annotations

import math

from plot_cut import geometry as g
from plot_cut.geometry import Polyline


def _square(x0=0.0, y0=0.0, size=10.0, ccw=True) -> Polyline:
    pts = [
        (x0, y0),
        (x0 + size, y0),
        (x0 + size, y0 + size),
        (x0, y0 + size),
        (x0, y0),
    ]
    if not ccw:
        pts = list(reversed(pts))
    return Polyline(pts, closed=True)


def test_signed_area_and_direction():
    sq = _square(ccw=True)
    assert sq.is_ccw()
    assert math.isclose(abs(sq.signed_area()) / 2.0, 100.0, rel_tol=1e-6)

    cw = _square(ccw=False)
    assert not cw.is_ccw()


def test_ensure_direction_flips():
    cw = _square(ccw=False)
    fixed = g.ensure_direction(cw, ccw=True)
    assert fixed.is_ccw()
    # Punktanzahl bleibt gleich
    assert len(fixed.points) == len(cw.points)


def test_flatten_cubic_straight_line():
    pts = g.flatten_cubic((0, 0), (10, 0), (20, 0), (30, 0), flatness=0.05)
    assert pts[-1] == (30, 0)
    # Alle Punkte liegen auf der x-Achse
    assert all(abs(y) < 1e-6 for _, y in pts)


def test_translate_and_move_to_origin():
    sq = _square(x0=5.0, y0=7.0, size=10.0)
    moved = g.move_to_origin([sq], margin=0.0)
    minx, miny, _, _ = g.bounds_of(moved)
    assert math.isclose(minx, 0.0, abs_tol=1e-9)
    assert math.isclose(miny, 0.0, abs_tol=1e-9)


def test_rotate_90():
    pl = Polyline([(0, 0), (10, 0)], closed=False)
    rot = g.rotate([pl], 90.0)[0]
    x, y = rot.points[1]
    assert math.isclose(x, 0.0, abs_tol=1e-9)
    assert math.isclose(y, 10.0, abs_tol=1e-9)


def test_mirror_x():
    pl = Polyline([(0, 0), (10, 0)], closed=False)
    m = g.mirror_x([pl], axis_x=5.0)[0]
    assert math.isclose(m.points[0][0], 10.0, abs_tol=1e-9)
    assert math.isclose(m.points[1][0], 0.0, abs_tol=1e-9)


def test_overcut_extends_closed_path():
    sq = _square(size=10.0)
    before = sq.length()
    oc = g.apply_overcut(sq, 2.0)
    assert oc.length() > before
    assert math.isclose(oc.length() - before, 2.0, abs_tol=1e-6)


def test_overcut_ignores_open_path():
    pl = Polyline([(0, 0), (10, 0)], closed=False)
    assert g.apply_overcut(pl, 2.0) is pl


def test_inner_first_sorting():
    outer = _square(x0=0.0, y0=0.0, size=100.0)
    inner = _square(x0=40.0, y0=40.0, size=20.0)
    ordered = g.sort_cut_order([outer, inner], inner_first=True, minimize_travel=False)
    assert ordered[0] is inner
    assert ordered[1] is outer


def test_prepare_job_bounds():
    sq = _square(x0=10.0, y0=10.0, size=30.0)
    job = g.prepare_job([sq], sort=False)
    assert math.isclose(job.width_mm, 30.0, abs_tol=1e-6)
    assert math.isclose(job.height_mm, 30.0, abs_tol=1e-6)


def test_svg_minimal_rect_import():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" '
        'viewBox="0 0 100 50"><rect x="10" y="10" width="20" height="15" '
        'stroke="#ff0000"/></svg>'
    )
    pls = g._polylines_from_svg_minimal(svg.encode(), 0.05)
    assert len(pls) == 1
    assert pls[0].closed
    assert pls[0].color == "#ff0000"
    x0, y0, x1, y1 = pls[0].bounds()
    assert math.isclose(x1 - x0, 20.0, abs_tol=1e-6)
    assert math.isclose(y1 - y0, 15.0, abs_tol=1e-6)


VECTORCRAFT_SVG = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" width="595.276" height="841.89" '
    'viewBox="0 0 595.276 841.89"><g id="Layer_1">'
    '<path d="M244.484 237.592 L329.523 237.592 L329.523 322.632 L244.484 322.632 Z" '
    'fill="#343334"/></g></svg>'
)


def test_vectorcraft_svg_is_in_points():
    """VectorCraft schreibt Breiten ohne Einheit in pt: 85,04 pt = 30 mm."""
    pls = g.polylines_from_svg(VECTORCRAFT_SVG.encode())
    assert len(pls) == 1
    x0, y0, x1, y1 = pls[0].bounds()
    assert math.isclose(x1 - x0, 30.0, abs_tol=0.01)
    assert math.isclose(y1 - y0, 30.0, abs_tol=0.01)
    assert pls[0].closed


def test_dxf_line_import():
    dxf = "0\nLINE\n10\n0.0\n20\n0.0\n11\n10.0\n21\n5.0\n0\nEOF\n"
    pls = g.polylines_from_dxf(dxf.encode())
    assert len(pls) == 1
    assert pls[0].points[0] == (0.0, 0.0)
    assert pls[0].points[1] == (10.0, 5.0)
