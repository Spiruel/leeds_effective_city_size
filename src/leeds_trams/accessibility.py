"""Population-weighted accessibility

For an era's network we compute, for every LSOA population-weighted centroid,
the door-to-door travel time from Leeds city centre (walk + ride + walk,
including waiting implied by the timetable), then sum population reachable
within each threshold.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from shapely.geometry import Point, mapping
from shapely.ops import unary_union

from . import (CENTRE_LAT, CENTRE_LON, EFFECTIVE_WALK_M_MIN,
               MAX_ACCESS_WALK_MIN)
from .geometry import haversine_m
from .router import Feed, raptor

THRESHOLDS = list(range(5, 65, 5))


def load_centroids(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            rows.append({"code": row["code"], "name": row["name"],
                         "lat": float(row["lat"]), "lon": float(row["lon"]),
                         "pop": float(row["population"])})
    return rows


def stop_travel_times(feed: Feed, dep_times_min: list[float],
                      origin: tuple[float, float] = (CENTRE_LAT, CENTRE_LON)) -> np.ndarray:
    """Average travel time (min) from the origin to every stop, over several
    departure times (reduces schedule luck)."""
    tts = []
    for t0 in dep_times_min:
        best = raptor(feed, origin[0], origin[1], t0)
        tts.append(best - t0)
    return np.mean(tts, axis=0)


def centroid_travel_times(feed: Feed, stop_tt: np.ndarray, centroids: list[dict],
                          origin: tuple[float, float] = (CENTRE_LAT, CENTRE_LON)) -> np.ndarray:
    """Door-to-door minutes from the origin to each centroid."""
    egress_radius = MAX_ACCESS_WALK_MIN * EFFECTIVE_WALK_M_MIN
    out = np.full(len(centroids), np.inf)
    for i, c in enumerate(centroids):
        # walking all the way
        walk = haversine_m(origin[0], origin[1], c["lat"], c["lon"]) / EFFECTIVE_WALK_M_MIN
        tt = walk
        for s, d in feed.stops_near(c["lat"], c["lon"], egress_radius):
            t = stop_tt[s] + d / EFFECTIVE_WALK_M_MIN
            if t < tt:
                tt = t
        out[i] = tt
    return out


def population_curve(centroid_tt: np.ndarray, centroids: list[dict]) -> dict[int, float]:
    pops = np.array([c["pop"] for c in centroids])
    return {t: float(pops[centroid_tt <= t].sum()) for t in THRESHOLDS}


def _to_local_xy(lat: float, lon: float) -> tuple[float, float]:
    x = (lon - CENTRE_LON) * 111_320 * math.cos(math.radians(CENTRE_LAT))
    y = (lat - CENTRE_LAT) * 110_540
    return x, y


def _to_latlon(x: float, y: float) -> tuple[float, float]:
    lat = CENTRE_LAT + y / 110_540
    lon = CENTRE_LON + x / (111_320 * math.cos(math.radians(CENTRE_LAT)))
    return lat, lon


def isochrone_geojson(feed: Feed, stop_tt: np.ndarray, threshold_min: float) -> tuple[dict, float]:
    """Union of walk-out discs around every stop reachable within the threshold
    (plus the walk disc around the origin). Returns (geojson_geometry, area_km2)."""
    discs = []
    r0 = min(threshold_min, MAX_ACCESS_WALK_MIN) * EFFECTIVE_WALK_M_MIN
    x, y = _to_local_xy(CENTRE_LAT, CENTRE_LON)
    discs.append(Point(x, y).buffer(r0, quad_segs=8))
    for s in range(feed.n_stops):
        remaining = threshold_min - stop_tt[s]
        if remaining <= 0:
            continue
        r = min(remaining, MAX_ACCESS_WALK_MIN) * EFFECTIVE_WALK_M_MIN
        if r < 30:
            continue
        x, y = _to_local_xy(feed.lat[s], feed.lon[s])
        discs.append(Point(x, y).buffer(r, quad_segs=8))
    union = unary_union(discs).simplify(20)
    area_km2 = union.area / 1e6

    def ring_to_latlon(ring):
        return [[round(lon, 6), round(lat, 6)] for x, y in ring.coords
                for lat, lon in [_to_latlon(x, y)]]

    geoms = list(union.geoms) if union.geom_type == "MultiPolygon" else [union]
    coords = [[ring_to_latlon(g.exterior)] + [ring_to_latlon(h) for h in g.interiors]
              for g in geoms]
    gj = {"type": "MultiPolygon", "coordinates": coords}
    return gj, area_km2


def analyse_era(gtfs_dir: Path, service_id: str | None, centroids: list[dict],
                dep_times_min: list[float], iso_thresholds=(15, 30, 45)) -> dict:
    feed = Feed(gtfs_dir, service_id=service_id)
    stop_tt = stop_travel_times(feed, dep_times_min)
    cen_tt = centroid_travel_times(feed, stop_tt, centroids)
    curve = population_curve(cen_tt, centroids)
    isochrones, areas = {}, {}
    for t in iso_thresholds:
        gj, area = isochrone_geojson(feed, stop_tt, t)
        isochrones[t] = gj
        areas[t] = round(area, 1)
    reachable_stops_30 = int((stop_tt <= 30).sum())
    return {
        "n_stops": feed.n_stops,
        "n_trips": feed.n_trips,
        "n_patterns": len(feed.pattern_stops),
        "stops_reachable_30min": reachable_stops_30,
        "population_curve": curve,
        "isochrone_area_km2": areas,
        "isochrones": isochrones,
        "centroid_tt": cen_tt,
        "stop_tt": stop_tt,
        "feed": feed,
    }
