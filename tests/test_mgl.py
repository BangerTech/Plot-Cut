"""Tests fuer den MGL-IIc/HP-GL-Generator."""

from __future__ import annotations

from plot_cut import mgl
from plot_cut.geometry import CutJob, Polyline
from plot_cut.mgl import CutCondition, PlotOptions


def test_mm_to_steps():
    assert mgl.mm_to_steps(1.0) == 40
    assert mgl.mm_to_steps(0.025) == 1
    assert mgl.mm_to_steps(10.0) == 400


def test_generate_basic_square():
    sq = Polyline([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], closed=True, color="#000000")
    job = CutJob(polylines=[sq], width_mm=10.0, height_mm=10.0)
    out = mgl.generate(
        job,
        default_condition=CutCondition(tool=1, speed=30, pressure=100, offset=0.3),
        options=PlotOptions(language="mgl2"),
    )
    lines = out.strip().splitlines()
    assert lines[0] == "IN;"
    assert "SP1;" in lines
    assert "VS30;" in lines
    assert "FS100;" in lines
    assert "!PT30;" in lines  # 0.3 mm * 100
    assert any(line.startswith("PU0,0;") for line in lines)
    assert any(line.startswith("PD") for line in lines)
    assert lines[-1] == "PU0,0;"


def test_pen_down_coordinates_in_steps():
    pl = Polyline([(0, 0), (10, 5)], closed=False, color="#000000")
    job = CutJob(polylines=[pl])
    out = mgl.generate(job, options=PlotOptions(emit_conditions=False))
    # PU0,0; dann PD400,200;
    assert "PU0,0;" in out
    assert "PD400,200;" in out


def test_copies_repeat_paths():
    pl = Polyline([(0, 0), (10, 0)], closed=False, color="#000000")
    job = CutJob(polylines=[pl])
    out = mgl.generate(job, options=PlotOptions(emit_conditions=False), copies=3)
    assert out.count("PD400,0;") == 3


def test_disabled_condition_skips_color():
    red = Polyline([(0, 0), (10, 0)], closed=False, color="#ff0000")
    job = CutJob(polylines=[red])
    out = mgl.generate(
        job,
        conditions_by_color={"#ff0000": CutCondition(enabled=False)},
        options=PlotOptions(),
    )
    assert "PD" not in out


def test_hpgl_has_no_offset_command():
    pl = Polyline([(0, 0), (10, 0)], closed=False, color="#000000")
    job = CutJob(polylines=[pl])
    out = mgl.generate(job, options=PlotOptions(language="hpgl"))
    assert "!PT" not in out
