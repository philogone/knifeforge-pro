"""Cubic Bézier -> circular arcs (biarc-style subdivision), for DXF exports with true arcs.

Laser, waterjet and CNC software prefer arcs to thousands of tiny segments: smoother motion,
smaller files. Each cubic segment is split until a circular arc through its two ends and its
midpoint stays within `tolerance` of the curve at every sampled point (default 0.01 mm, the
project's curve tolerance). Straight runs become lines (bulge 0).
"""

from __future__ import annotations

import math

Point = tuple[float, float]
SAMPLES = 24  # points checked per candidate arc
MAX_DEPTH = 14


def _lerp(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def cubic_point(p0: Point, c1: Point, c2: Point, p1: Point, t: float) -> Point:
    mt = 1 - t
    a, b, c, d = mt * mt * mt, 3 * mt * mt * t, 3 * mt * t * t, t * t * t
    return (a * p0[0] + b * c1[0] + c * c2[0] + d * p1[0], a * p0[1] + b * c1[1] + c * c2[1] + d * p1[1])


def _split(p0: Point, c1: Point, c2: Point, p1: Point) -> tuple[tuple[Point, Point, Point, Point], tuple[Point, Point, Point, Point]]:
    """de Casteljau at t = 0.5."""
    ab, bc, cd = _lerp(p0, c1, 0.5), _lerp(c1, c2, 0.5), _lerp(c2, p1, 0.5)
    abc, bcd = _lerp(ab, bc, 0.5), _lerp(bc, cd, 0.5)
    mid = _lerp(abc, bcd, 0.5)
    return (p0, ab, abc, mid), (mid, bcd, cd, p1)


def _circle(a: Point, b: Point, c: Point) -> tuple[Point, float] | None:
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = a[0] ** 2 + a[1] ** 2, b[0] ** 2 + b[1] ** 2, c[0] ** 2 + c[1] ** 2
    ux = (a2 * (b[1] - c[1]) + b2 * (c[1] - a[1]) + c2 * (a[1] - b[1])) / d
    uy = (a2 * (c[0] - b[0]) + b2 * (a[0] - c[0]) + c2 * (b[0] - a[0])) / d
    return (ux, uy), math.hypot(a[0] - ux, a[1] - uy)


def _angle(center: Point, p: Point) -> float:
    return math.atan2(p[1] - center[1], p[0] - center[0])


def _wrap(a: float) -> float:
    while a <= -math.pi:
        a += 2 * math.pi
    while a > math.pi:
        a -= 2 * math.pi
    return a


def _distance_to_segment(p: Point, a: Point, b: Point) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    length2 = vx * vx + vy * vy
    if length2 == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / length2))
    return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


def cubic_to_arcs(p0: Point, c1: Point, c2: Point, p1: Point, tolerance: float, depth: int = 0) -> list[tuple[Point, float]]:
    """[(end point, bulge)] covering the curve from p0; bulge = tan(sweep / 4), > 0 counter-clockwise."""
    samples = [cubic_point(p0, c1, c2, p1, i / SAMPLES) for i in range(1, SAMPLES)]

    # a straight run: one line
    if all(_distance_to_segment(s, p0, p1) <= tolerance for s in samples):
        return [(p1, 0.0)]

    mid = cubic_point(p0, c1, c2, p1, 0.5)
    fit = _circle(p0, mid, p1)
    if fit is not None and depth < MAX_DEPTH:
        center, radius = fit
        sweep = _wrap(_angle(center, mid) - _angle(center, p0)) + _wrap(_angle(center, p1) - _angle(center, mid))
        if abs(sweep) < math.pi * 0.95:
            ok = True
            a0 = _angle(center, p0)
            for s in samples:
                if abs(math.hypot(s[0] - center[0], s[1] - center[1]) - radius) > tolerance:
                    ok = False
                    break
                # the sample must also fall inside the arc's angular span
                rel = _wrap(_angle(center, s) - a0)
                if sweep > 0 and not (-1e-9 <= rel <= sweep + 1e-9) or sweep < 0 and not (sweep - 1e-9 <= rel <= 1e-9):
                    ok = False
                    break
            if ok:
                return [(p1, math.tan(sweep / 4))]
    if depth >= MAX_DEPTH:
        return [(p1, 0.0)]  # unreachable in practice: segments this small are straight within tolerance
    left, right = _split(p0, c1, c2, p1)
    return cubic_to_arcs(*left, tolerance, depth + 1) + cubic_to_arcs(*right, tolerance, depth + 1)
