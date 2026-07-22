"""Geometric helpers: haversine, polyline resampling, point projection."""

from __future__ import annotations

import math

EARTH_R = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return EARTH_R * 2 * math.asin(math.sqrt(a))


def cumulative_dist_m(points: list[tuple[float, float]]) -> list[float]:
    """Cumulative distance along a (lat, lon) polyline."""
    out = [0.0]
    for (a, b), (c, d) in zip(points, points[1:]):
        out.append(out[-1] + haversine_m(a, b, c, d))
    return out


def point_at_dist(points: list[tuple[float, float]], cum: list[float], d: float) -> tuple[float, float]:
    """Interpolate the point at distance d along the polyline."""
    d = max(0.0, min(d, cum[-1]))
    for i in range(1, len(cum)):
        if cum[i] >= d:
            seg = cum[i] - cum[i - 1]
            f = 0.0 if seg == 0 else (d - cum[i - 1]) / seg
            lat = points[i - 1][0] + f * (points[i][0] - points[i - 1][0])
            lon = points[i - 1][1] + f * (points[i][1] - points[i - 1][1])
            return lat, lon
    return points[-1]


def project_onto_polyline(points: list[tuple[float, float]], cum: list[float],
                          lat: float, lon: float) -> float:
    """Distance along the polyline of the closest vertex-sampled position to (lat, lon).
    """
    best_d, best_at = float("inf"), 0.0
    step = 25.0
    d = 0.0
    while d <= cum[-1]:
        plat, plon = point_at_dist(points, cum, d)
        dist = haversine_m(lat, lon, plat, plon)
        if dist < best_d:
            best_d, best_at = dist, d
        d += step
    return best_at


def resample_polyline(points: list[tuple[float, float]], spacing_m: float,
                      anchors_m: list[float] | None = None) -> list[tuple[float, tuple[float, float]]]:
    """Return [(dist_m, (lat, lon)), ...] every spacing_m along the line.

    `anchors_m` are distances that must appear exactly (timing points); regular
    samples closer than 0.4*spacing to an anchor are dropped in its favour.
    """
    cum = cumulative_dist_m(points)
    total = cum[-1]
    anchors = sorted(set([0.0, total] + (list(anchors_m) if anchors_m else [])))
    samples = list(anchors)
    d = spacing_m
    while d < total:
        if min(abs(d - a) for a in anchors) > 0.4 * spacing_m:
            samples.append(d)
        d += spacing_m
    samples.sort()
    return [(s, point_at_dist(points, cum, s)) for s in samples]


class GridIndex:
    """Simple lat/lon grid for radius queries (cell ~ radius)."""

    def __init__(self, radius_m: float):
        self.radius_m = radius_m
        self.cell_deg = radius_m / 111_000.0
        self.cells: dict[tuple[int, int], list[int]] = {}
        self.pts: list[tuple[float, float]] = []

    def _key(self, lat: float, lon: float) -> tuple[int, int]:
        return (int(lat / self.cell_deg), int(lon / (self.cell_deg)))

    def add(self, lat: float, lon: float) -> int:
        idx = len(self.pts)
        self.pts.append((lat, lon))
        self.cells.setdefault(self._key(lat, lon), []).append(idx)
        return idx

    def near(self, lat: float, lon: float, radius_m: float | None = None):
        """Yield (idx, dist_m) for points within radius."""
        r = radius_m if radius_m is not None else self.radius_m
        span_lat = int(r / (self.cell_deg * 111_000.0)) + 1
        # 1 deg of longitude is ~65 km at Leeds latitude, so search more lon cells
        span_lon = int(r / (self.cell_deg * 65_000.0)) + 1
        k0, k1 = self._key(lat, lon)
        for i in range(k0 - span_lat, k0 + span_lat + 1):
            for j in range(k1 - span_lon, k1 + span_lon + 1):
                for idx in self.cells.get((i, j), ()):
                    plat, plon = self.pts[idx]
                    d = haversine_m(lat, lon, plat, plon)
                    if d <= r:
                        yield idx, d
