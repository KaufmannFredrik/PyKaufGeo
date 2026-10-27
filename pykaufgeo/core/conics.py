"""Conic geometry: canonical form, parameterisation, sampling and intersections.

A conic is ``A x² + B xy + C y² + D x + E y + F = 0``. ``shape_of`` finds its kind and
an orthonormal frame (u along the first principal axis, v perpendicular):

* ellipse / circle: centre c, semi-axes a >= b;  X(t) = c + a cos t u + b sin t v
* hyperbola: centre c, transverse semi-axis a along u, b;
  branches X = c ± a cosh(s) u + b sinh(s) v. One path parameter t in [-pi/2, 3pi/2)
  covers both: t < pi/2 is the right branch with s = tan(t), otherwise the left
  branch with s = tan(t - pi).
* parabola: X(s) = s w + r(s) u, from the eigenvector w of the non-zero eigenvalue.
* degenerate: intersecting or parallel lines (as line coefficients), a single point, empty.

Everything here is plain numpy and used by paths, commands, transformations and drawing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

Coeffs = tuple[float, float, float, float, float, float]
REL = 1e-10


@dataclass(frozen=True)
class ConicShape:
    kind: str                      # ellipse, circle, hyperbola, parabola, lines, point, empty
    cx: float = 0.0
    cy: float = 0.0
    ux: float = 1.0                # first principal axis
    uy: float = 0.0
    a: float = 0.0
    b: float = 0.0
    # parabola: X(s) = s w + (p2 s² + p1 s + p0) u, with w = (-uy, ux)
    p2: float = 0.0
    p1: float = 0.0
    p0: float = 0.0
    lines: tuple[tuple[float, float, float], ...] = field(default_factory=tuple)

    @property
    def vx(self) -> float:
        return -self.uy

    @property
    def vy(self) -> float:
        return self.ux


def evaluate(c: Coeffs, x, y):
    A, B, C, D, E, F = c
    return A * x * x + B * x * y + C * y * y + D * x + E * y + F


def normalised(c: Coeffs) -> Coeffs:
    s = max(abs(k) for k in c) or 1.0
    return tuple(k / s for k in c)  # type: ignore[return-value]


def shape_of(coeffs: Coeffs) -> ConicShape:
    A, B, C, D, E, F = normalised(coeffs)
    M = np.array([[A, B / 2], [B / 2, C]])
    lam, vec = np.linalg.eigh(M)
    scale = max(abs(lam[0]), abs(lam[1]), 1e-300)
    l0, l1 = (0.0 if abs(lam[0]) < 1e-9 * scale else lam[0]), (0.0 if abs(lam[1]) < 1e-9 * scale else lam[1])
    if l0 != 0.0 and l1 != 0.0:
        cx, cy = np.linalg.solve(M, [-D / 2, -E / 2])
        Fp = F + (D * cx + E * cy) / 2
        if abs(Fp) < 1e-12:
            if l0 * l1 > 0:
                return ConicShape("point", cx, cy)
            # two lines through the centre: l0 s² + l1 r² = 0
            k = math.sqrt(-l0 / l1)
            u, v = vec[:, 0], vec[:, 1]
            lines = []
            for sign in (1, -1):
                # direction d = u + sign*k*v ... the line r = sign*k*s in (s along u, r along v) coordinates
                dx, dy = u[0] + sign * k * v[0], u[1] + sign * k * v[1]
                lines.append(_line_through(cx, cy, dx, dy))
            return ConicShape("lines", cx, cy, lines=tuple(lines))
        a2, b2 = -Fp / l0, -Fp / l1
        if a2 > 0 and b2 > 0:
            # ellipse: major axis first
            if a2 >= b2:
                u, a, b = vec[:, 0], math.sqrt(a2), math.sqrt(b2)
            else:
                u, a, b = vec[:, 1], math.sqrt(b2), math.sqrt(a2)
            kind = "circle" if abs(a - b) <= 1e-9 * max(a, 1.0) else "ellipse"
            return ConicShape(kind, cx, cy, u[0], u[1], a, b)
        if a2 < 0 and b2 < 0:
            return ConicShape("empty", cx, cy)
        # hyperbola: transverse axis where the squared semi-axis is positive
        if a2 > 0:
            u, a, b = vec[:, 0], math.sqrt(a2), math.sqrt(-b2)
        else:
            u, a, b = vec[:, 1], math.sqrt(b2), math.sqrt(-a2)
        return ConicShape("hyperbola", cx, cy, u[0], u[1], a, b)
    if l0 == 0.0 and l1 == 0.0:
        return ConicShape("empty")  # not a conic (linear); callers treat lines separately
    # parabola or parallel lines: lam w-direction non-zero, u-direction zero
    if l0 == 0.0:
        u, w, lam_w = vec[:, 0], vec[:, 1], l1
    else:
        u, w, lam_w = vec[:, 1], vec[:, 0], l0
    # make w = (-uy, ux) so the frame is right-handed
    if abs(w[0] + u[1]) > 1e-9 or abs(w[1] - u[0]) > 1e-9:
        u = -u
    dw = D * w[0] + E * w[1]
    du = D * u[0] + E * u[1]
    if abs(du) < 1e-12:
        disc = dw * dw - 4 * lam_w * F
        if disc < -1e-12:
            return ConicShape("empty")
        roots = sorted({(-dw + sg * math.sqrt(max(disc, 0.0))) / (2 * lam_w) for sg in (1, -1)})
        lines = tuple((w[0], w[1], -s0) for s0 in roots)   # w·X = s0
        return ConicShape("lines", lines=lines)
    # lam s² + dw s + du r + F = 0  ->  r = -(lam s² + dw s + F) / du
    return ConicShape("parabola", 0.0, 0.0, u[0], u[1], p2=-lam_w / du, p1=-dw / du, p0=-F / du)


def _line_through(cx: float, cy: float, dx: float, dy: float) -> tuple[float, float, float]:
    return (-dy, dx, dy * cx - dx * cy)


# ----------------------------------------------------------------------- parameterisation

def param_range(shape: ConicShape) -> tuple[float, float, bool]:
    """(t0, t1, closed) for a path parameter on the conic."""
    if shape.kind in ("ellipse", "circle"):
        return (0.0, 2 * math.pi, True)
    if shape.kind == "hyperbola":
        return (-math.pi / 2, 3 * math.pi / 2, True)
    return (-math.inf, math.inf, False)


def point_at(shape: ConicShape, t: float) -> tuple[float, float]:
    k = shape.kind
    if k in ("ellipse", "circle"):
        ca, sa = math.cos(t) * shape.a, math.sin(t) * shape.b
        return (shape.cx + ca * shape.ux + sa * shape.vx, shape.cy + ca * shape.uy + sa * shape.vy)
    if k == "hyperbola":
        t = (t + math.pi / 2) % (2 * math.pi) - math.pi / 2
        right = t < math.pi / 2
        s = math.tan(t if right else t - math.pi)
        sign = 1.0 if right else -1.0
        ch, sh = sign * shape.a * math.cosh(s), shape.b * math.sinh(s)
        return (shape.cx + ch * shape.ux + sh * shape.vx, shape.cy + ch * shape.uy + sh * shape.vy)
    if k == "parabola":
        r = shape.p2 * t * t + shape.p1 * t + shape.p0
        return (t * shape.vx + r * shape.ux, t * shape.vy + r * shape.uy)
    return (math.nan, math.nan)


def points_at(shape: ConicShape, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised ``point_at``."""
    k = shape.kind
    with np.errstate(all="ignore"):
        if k in ("ellipse", "circle"):
            ca, sa = np.cos(t) * shape.a, np.sin(t) * shape.b
            return (shape.cx + ca * shape.ux + sa * shape.vx, shape.cy + ca * shape.uy + sa * shape.vy)
        if k == "hyperbola":
            t = np.mod(t + np.pi / 2, 2 * np.pi) - np.pi / 2
            right = t < np.pi / 2
            s = np.tan(np.where(right, t, t - np.pi))
            sign = np.where(right, 1.0, -1.0)
            ch, sh = sign * shape.a * np.cosh(s), shape.b * np.sinh(s)
            return (shape.cx + ch * shape.ux + sh * shape.vx, shape.cy + ch * shape.uy + sh * shape.vy)
        if k == "parabola":
            r = shape.p2 * t * t + shape.p1 * t + shape.p0
            return (t * shape.vx + r * shape.ux, t * shape.vy + r * shape.uy)
    return (np.full(t.shape, np.nan), np.full(t.shape, np.nan))


def project(shape: ConicShape, x: float, y: float) -> float:
    """Parameter of the conic point closest to (x, y) (dense search, then refinement)."""
    k = shape.kind
    if k in ("ellipse", "circle", "hyperbola"):
        t0, t1, _ = param_range(shape)
        ts = np.linspace(t0, t1, 2049)[:-1]
    elif k == "parabola":
        # s is the coordinate along w: start around the projection of the point
        s0 = x * shape.vx + y * shape.vy
        span = 10 * (abs(s0) + 10)
        ts = np.concatenate([np.linspace(s0 - span, s0 + span, 2001), [s0]])
    else:
        return 0.0
    px, py = points_at(shape, ts)
    d = np.hypot(px - x, py - y)
    d = np.where(np.isfinite(d), d, np.inf)
    i = int(np.argmin(d))
    lo = ts[max(i - 1, 0)]
    hi = ts[min(i + 1, len(ts) - 1)]
    for _ in range(60):  # golden-section refinement
        m1, m2 = lo + (hi - lo) * 0.382, lo + (hi - lo) * 0.618
        d1 = math.hypot(*np.subtract(point_at(shape, m1), (x, y)))
        d2 = math.hypot(*np.subtract(point_at(shape, m2), (x, y)))
        if d1 < d2:
            hi = m2
        else:
            lo = m1
    return (lo + hi) / 2


# ----------------------------------------------------------------------- drawing samples

def sample(shape: ConicShape, reach: float, n: int = 721) -> list[tuple[np.ndarray, np.ndarray]]:
    """World-space polylines covering the conic within ``reach`` of the conic's frame origin.

    ``reach`` should be at least the distance from the centre to the farthest view
    corner, so unbounded branches leave the view.
    """
    k = shape.kind
    if k in ("ellipse", "circle"):
        t = np.linspace(0, 2 * np.pi, n)
        return [points_at(shape, t)]
    if k == "hyperbola":
        smax = math.asinh(max(reach, 1.0) / max(shape.b, 1e-12)) + 0.5
        s = np.sinh(np.linspace(-math.asinh(smax * 10), math.asinh(smax * 10), n)) / 10
        s = np.clip(s, -smax, smax)
        out = []
        for sign in (1.0, -1.0):
            ch, sh = sign * shape.a * np.cosh(s), shape.b * np.sinh(s)
            out.append((shape.cx + ch * shape.ux + sh * shape.vx, shape.cy + ch * shape.uy + sh * shape.vy))
        return out
    if k == "parabola":
        vertex_s = -shape.p1 / (2 * shape.p2) if shape.p2 else 0.0
        span = math.sqrt(max(reach, 1.0) / max(abs(shape.p2), 1e-12)) + reach
        s = vertex_s + np.sinh(np.linspace(-1, 1, n) * math.asinh(span)) * 1.0
        return [points_at(shape, s)]
    return []


# ----------------------------------------------------------------------- intersections

def _refine_roots(f, ts: np.ndarray, vals: np.ndarray) -> list[float]:
    roots = []
    for i in range(len(ts) - 1):
        a, b, fa, fb = ts[i], ts[i + 1], vals[i], vals[i + 1]
        if not (np.isfinite(fa) and np.isfinite(fb)):
            continue
        if fa == 0:
            roots.append(a)
        elif fa * fb < 0:
            for _ in range(80):
                m = (a + b) / 2
                fm = f(m)
                if fa * fm <= 0:
                    b, fb = m, fm
                else:
                    a, fa = m, fm
            roots.append((a + b) / 2)
    # tangencies: local minima of |f| close to zero
    absv = np.abs(vals)
    for i in range(1, len(ts) - 1):
        if np.isfinite(absv[i]) and absv[i] <= absv[i - 1] and absv[i] <= absv[i + 1]:
            lo, hi = ts[i - 1], ts[i + 1]
            for _ in range(80):
                m1, m2 = lo + (hi - lo) * 0.382, lo + (hi - lo) * 0.618
                if abs(f(m1)) < abs(f(m2)):
                    hi = m2
                else:
                    lo = m1
            m = (lo + hi) / 2
            if abs(f(m)) < 1e-9 and all(abs(m - r) > 1e-6 for r in roots):
                roots.append(m)
    return roots


def intersect_conics(c1: Coeffs, c2: Coeffs) -> list[tuple[float, float]]:
    """Intersection points of two conics (up to four), found along a parameterisation."""
    s1, s2 = shape_of(c1), shape_of(c2)
    if s1.kind not in ("ellipse", "circle") and s2.kind in ("ellipse", "circle"):
        s1, c1, c2 = s2, c2, c1
    if s1.kind in ("ellipse", "circle"):
        ts = np.linspace(0, 2 * np.pi, 2881)
    elif s1.kind == "hyperbola":
        ts = np.linspace(-math.pi / 2 + 1e-9, 3 * math.pi / 2 - 1e-9, 4001)
    elif s1.kind == "parabola":
        ts = np.sinh(np.linspace(-12, 12, 4001))
    else:
        return []
    n2 = normalised(c2)

    def f(t: float) -> float:
        x, y = point_at(s1, t)
        return evaluate(n2, x, y)

    xs, ys = points_at(s1, ts)
    vals = evaluate(n2, xs, ys)
    pts = []
    for t in _refine_roots(f, ts, vals):
        x, y = point_at(s1, t)
        if all(math.hypot(x - px, y - py) > 1e-7 for px, py in pts):
            pts.append((x, y))
    pts.sort()
    return pts[:4]


def conic_from_axes(cx: float, cy: float, ux: float, uy: float, alpha: float, beta: float,
                    gamma: float) -> Coeffs:
    """Coefficients of alpha (u·(X-c))² + beta (v·(X-c))² + gamma = 0, v = (-uy, ux)."""
    vx, vy = -uy, ux
    A = alpha * ux * ux + beta * vx * vx
    B = 2 * (alpha * ux * uy + beta * vx * vy)
    C = alpha * uy * uy + beta * vy * vy
    # linear terms from expanding around the centre
    D = -2 * A * cx - B * cy
    E = -B * cx - 2 * C * cy
    F = A * cx * cx + B * cx * cy + C * cy * cy + gamma
    return (A, B, C, D, E, F)


def conic_through_points(pts: list[tuple[float, float]]) -> Coeffs | None:
    """The conic through five points (None if they do not determine one)."""
    M = np.array([[x * x, x * y, y * y, x, y, 1.0] for x, y in pts])
    _, s, vt = np.linalg.svd(M)
    if s[-1] > 1e-9 * s[0] and len(pts) > 5:
        return None
    if s[3] < 1e-10 * s[0]:
        return None  # four or more collinear points: not unique
    coeffs = vt[-1]
    return tuple(float(k) for k in coeffs / np.max(np.abs(coeffs)))  # type: ignore[return-value]
