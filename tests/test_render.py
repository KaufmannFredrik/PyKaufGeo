"""Qt-free rendering geometry: viewport, ticks, adaptive sampling, clipping, labels."""

from __future__ import annotations

import math

import numpy as np
import pytest

from pykaufgeo.render.clip import clip_segment, line_on_screen, ray_on_screen, segment_on_screen
from pykaufgeo.render.labels import overlaps, place_label
from pykaufgeo.render.sampling import MAX_POINTS, evaluate, sample_function
from pykaufgeo.render.viewport import Viewport, format_tick, minor_step, nice_step, ticks

VP = Viewport.standard(1000, 700)  # x in [-10, 10], y in [-7, 7], 50 px per unit


# ------------------------------------------------------------------ viewport

def test_standard_view_and_mapping() -> None:
    assert (VP.xmin, VP.xmax, VP.ymin, VP.ymax) == (-10, 10, -7, 7)
    assert VP.to_screen(0, 0) == (500, 350)
    assert VP.to_world(500, 350) == (0, 0)
    sx, sy = VP.to_screen(np.array([1.0, -2.0]), np.array([1.0, 0.0]))
    assert list(sx) == [550, 400] and list(sy) == [300, 350]


def test_zoom_keeps_point_under_cursor() -> None:
    for factor in (1.5, 0.5, 10.0):
        z = VP.zoomed(123, 456, factor)
        assert z.wx(123) == pytest.approx(VP.wx(123)) and z.wy(456) == pytest.approx(VP.wy(456))
        assert z.xscale == pytest.approx(VP.xscale * factor)
    stretched = VP.zoomed(500, 350, 2.0, 1.0)
    assert stretched.xscale == 100 and stretched.yscale == 50


def test_pan_resize_rect_zoom_ratio() -> None:
    p = VP.panned(50, -100)
    assert p.wx(550) == pytest.approx(VP.wx(500)) and p.wy(250) == pytest.approx(VP.wy(350))
    r = VP.resized(500, 300)
    assert (r.xmin, r.ymax, r.xscale) == (VP.xmin, VP.ymax, VP.xscale)
    z = VP.zoomed_to(0, 0, 4, 1, keep_ratio=True)
    assert z.xscale == pytest.approx(z.yscale) and z.xmin <= 0 and z.xmax >= 4 and z.ymin <= 0 and z.ymax >= 1
    free = VP.zoomed_to(0, 0, 4, 1, keep_ratio=False)
    assert free.xmin == pytest.approx(0) and free.xmax == pytest.approx(4) and free.ymax == pytest.approx(1)
    skew = VP.zoomed(0, 0, 1.0, 3.0).with_ratio(1.0)
    assert skew.yscale == skew.xscale


def test_settings_round_trip_and_bad_values() -> None:
    again = Viewport.from_settings(VP.settings(), 1000, 700)
    assert again == VP
    bad = Viewport.from_settings({"xmin": "nope", "xscale": float("nan"), "yscale": -5}, 100, 100)
    assert math.isfinite(bad.xmin) and bad.xscale > 0 and bad.yscale > 0


@pytest.mark.parametrize("ppu,expected", [(50, 1), (100, 0.5), (10, 5), (500, 0.1), (1, 50), (0.03, 2000), (2e5, 5e-4)])
def test_nice_step_is_1_2_5(ppu: float, expected: float) -> None:
    step = nice_step(ppu)
    assert step == pytest.approx(expected)
    assert step * ppu >= 45 - 1e-9
    mant = step / 10 ** math.floor(math.log10(step))
    assert round(mant, 6) in (1, 2, 5)


def test_minor_steps_and_ticks() -> None:
    assert minor_step(1) == 0.2 and minor_step(2) == 0.5 and minor_step(5) == 1
    assert list(ticks(-1.2, 3.1, 1)) == [-1, 0, 1, 2, 3]
    assert len(ticks(0, 1, 0)) == 0
    assert format_tick(0.30000000000000004, 0.1) == "0.3" and format_tick(-2, 1) == "-2"
    assert format_tick(1e-6, 1e-6) == "1E-6" and format_tick(0, 5) == "0"


# ------------------------------------------------------------------ sampling

def _max_jump(pieces) -> float:
    return max((float(np.max(np.abs(np.diff(sy)))) for _, sy in pieces if len(sy) > 1), default=0.0)


def _crosses_view(pieces, vp: Viewport) -> bool:
    """Does any drawn segment run from above the view to below it (a false vertical spike)?"""
    for _, sy in pieces:
        a, b = sy[:-1], sy[1:]
        if np.any(((a < 0) & (b > vp.height)) | ((a > vp.height) & (b < 0))):
            return True
    return False


def test_tan_breaks_at_every_pole() -> None:
    pieces = sample_function(np.tan, VP)
    assert len(pieces) == 7  # poles at +-pi/2, +-3pi/2, +-5pi/2 inside [-10, 10]
    poles = [math.pi / 2 + k * math.pi for k in range(-4, 4)]
    for sx, _ in pieces:
        lo, hi = VP.wx(sx[0]), VP.wx(sx[-1])
        assert not any(lo < pole < hi for pole in poles), (lo, hi)  # no piece spans a pole
    # no segment runs from the top to the bottom of the view
    assert not _crosses_view(pieces, VP)


def test_reciprocal_floor_sign_jumps() -> None:
    assert len(sample_function(lambda x: 1 / x, VP)) == 2
    assert len(sample_function(np.floor, VP)) == 20
    sign = sample_function(np.sign, VP)
    assert len(sign) >= 2 and _max_jump(sign) < 5


def test_domain_edges_are_reached() -> None:
    (sx, sy), = sample_function(np.sqrt, VP)
    assert VP.wx(sx[0]) == pytest.approx(0, abs=1e-6)
    (lx, ly), = sample_function(np.log, VP)
    assert VP.wx(lx[0]) == pytest.approx(0, abs=1e-6) and ly[0] > VP.height  # runs off the bottom
    assert len(sample_function(lambda x: 1 / x ** 2, VP)) == 2


def test_continuous_steep_curve_is_one_piece_and_refined() -> None:
    pieces = sample_function(lambda x: x ** 3, VP)
    assert len(pieces) == 1
    wiggly = sample_function(lambda x: np.sin(30 * x), VP)
    assert len(wiggly) == 1 and len(wiggly[0][0]) > 600
    assert sum(len(p[0]) for p in sample_function(lambda x: np.sin(1000 * x), VP)) <= MAX_POINTS + 200


def test_undefined_constant_complex_and_errors() -> None:
    assert sample_function(lambda x: np.full_like(x, np.nan), VP) == []
    (sx, sy), = sample_function(lambda x: 3.0, VP)
    assert np.allclose(sy, VP.sy(3.0))
    assert np.isnan(evaluate(lambda x: x * 1j, np.array([1.0]))[0])  # non-real values are undefined
    assert evaluate(lambda x: x + 0j, np.array([2.0]))[0] == 2.0

    def boom(x):
        raise RuntimeError("broken function")

    assert sample_function(boom, VP) == []


def test_sampling_respects_restricted_range() -> None:
    (sx, _), = sample_function(lambda x: x, VP, x0=-1, x1=2)
    assert VP.wx(sx[0]) == pytest.approx(-1) and VP.wx(sx[-1]) == pytest.approx(2)
    assert sample_function(lambda x: x, VP, x0=20, x1=30) == []


# ------------------------------------------------------------------ clipping

def test_clip_segment() -> None:
    assert clip_segment(-10, 5, 110, 5, 0, 0, 100, 100) == ((0, 5), (100, 5))
    assert clip_segment(-10, -10, -5, -5, 0, 0, 100, 100) is None
    assert clip_segment(10, 10, 20, 20, 0, 0, 100, 100) == ((10, 10), (20, 20))


def test_lines_rays_segments_on_screen() -> None:
    seg = line_on_screen(0, 1, 0, VP)  # y = 0
    assert seg is not None
    (x0, y0), (x1, y1) = seg
    assert y0 == pytest.approx(350) and y1 == pytest.approx(350) and min(x0, x1) <= 0 and max(x0, x1) >= 1000
    assert line_on_screen(0, 1, -100, VP) is None  # y = 100 is off screen
    assert line_on_screen(0, 0, 1, VP) is None
    (rx0, ry0), (rx1, ry1) = ray_on_screen(0, 0, 1, 0, VP)
    assert rx0 == pytest.approx(500) and ry0 == pytest.approx(350) and rx1 >= 1000
    (a, b) = segment_on_screen(0, 0, 1, 1, VP)
    assert (*a, *b) == pytest.approx((500, 350, 550, 300))


# ------------------------------------------------------------------ labels

def test_label_placement_avoids_overlap() -> None:
    occupied = []
    a = place_label(100, 100, 20, 12, occupied, 4)
    occupied.append(a)
    b = place_label(102, 101, 20, 12, occupied, 4)
    assert not overlaps(a, b)
    edge = place_label(995, 5, 20, 12, [], 4, bounds=(0, 0, 1000, 700))
    assert edge[0] + edge[2] <= 1000 and edge[1] >= 0


def test_decimation_keeps_shape_and_drops_collinear_points() -> None:
    from pykaufgeo.render.sampling import decimate

    sx = np.linspace(0, 1000, 1001)
    sy = 300 + 100 * np.sin(sx / 80)
    dx, dy = decimate(sx, sy)
    assert len(dx) < len(sx) / 3
    # every original point lies within 1 px of the simplified polyline
    yi = np.interp(sx, dx, dy)
    assert np.max(np.abs(yi - sy)) < 1.0
    lx, ly = decimate(np.linspace(0, 10, 50), np.linspace(0, 10, 50))
    assert len(lx) <= 3 and lx[0] == 0 and lx[-1] == 10
