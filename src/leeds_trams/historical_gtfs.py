"""Build GTFS feeds for the 1956/57 Leeds network (trams, buses, or both).

Inputs:
  data/transcriptions/p*.json           tram page transcriptions
  data/historical/route_geometry.json   tram street alignments
  data/historical/bus_lines.json        merged bus transcriptions
  data/historical/bus_route_geometry_*.json  bus street alignments

The timetable book gives times at major timing points only. Stops are
interpolated every STOP_SPACING_M along each route's polyline; times are
interpolated by distance between timing points, per direction (running times
were asymmetric). Directions whose printed stop names don't exactly mirror
the geometry's timing points are anchored on the matching subset.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from .geometry import (GridIndex, cumulative_dist_m, project_onto_polyline,
                       resample_polyline)
from .transcripts import canonical_stop, expand_pattern, load_transcriptions

STOP_SPACING_M = 300.0
STOP_MERGE_M = 60.0

DAY_TYPE_SERVICES = {
    "monday_to_friday": ["weekday"],
    "saturday": ["saturday"],
    "sunday": ["sunday"],
    "monday_to_saturday": ["weekday", "saturday"],
    "daily": ["weekday", "saturday", "sunday"],
}

TRAM_META = {
    "p08": {"short": "MC", "color": "C0392B"},
    "p09": {"short": "MR", "color": "E67E22"},
    "p10": {"short": "DR", "color": "27AE60"},
    "p11": {"short": "HM", "color": "2980B9"},
    "p12": {"short": "XM", "color": "8E44AD"},
    "p13": {"short": "TN", "color": "16A085"},
    "p14": {"short": "HU", "color": "D35400"},
}


class StopRegistry:
    """Global stop pool; stops within STOP_MERGE_M are shared across routes."""

    def __init__(self):
        self.grid = GridIndex(STOP_MERGE_M)
        self.stops: list[dict] = []

    def get(self, lat: float, lon: float, name: str, is_timing_point: bool) -> str:
        for idx, _d in sorted(self.grid.near(lat, lon, STOP_MERGE_M), key=lambda x: x[1]):
            stop = self.stops[idx]
            if is_timing_point and not stop["timing_point"]:
                stop["name"], stop["timing_point"] = name, True
            return stop["id"]
        idx = self.grid.add(lat, lon)
        stop = {"id": f"HS{idx:04d}", "name": name, "lat": lat, "lon": lon,
                "timing_point": is_timing_point}
        self.stops.append(stop)
        return stop["id"]


def _interp_extrap(d: float, anchor_d: list[float], anchor_t: list[float]) -> float:
    """Piecewise-linear time at distance d; linear extrapolation past the ends
    using the adjacent segment's speed (clamped non-negative)."""
    if len(anchor_d) == 1:
        return anchor_t[0]

    def slope(i: int, j: int) -> float:
        dd = anchor_d[j] - anchor_d[i]
        return (anchor_t[j] - anchor_t[i]) / dd if dd > 0 else 0.0

    if d <= anchor_d[0]:
        return max(0.0, anchor_t[0] - slope(0, 1) * (anchor_d[0] - d))
    for i in range(1, len(anchor_d)):
        if d <= anchor_d[i]:
            return anchor_t[i - 1] + slope(i - 1, i) * (d - anchor_d[i - 1])
    return anchor_t[-1] + slope(len(anchor_d) - 2, len(anchor_d) - 1) * (d - anchor_d[-1])


def _min_to_gtfs(m: float) -> str:
    s = int(round(m * 60))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _direction_anchors(names: list[str], offsets: list[float],
                       tp_names: list[str], tp_dist: list[float],
                       total: float) -> tuple[list[float], list[float], bool] | None:
    """Match a printed direction's stops onto the route's timing points.

    Returns (anchor_traversal_dist, anchor_time, is_reverse), where traversal
    distance is measured along the direction of travel. None if fewer than two
    stops match the timing points.
    """
    cn = [canonical_stop(n) for n in names]

    def ordered_match(tps: list[str]) -> list[tuple[int, int]]:
        """Greedy in-order alignment of stop names onto timing points; handles
        circular routes where the same name appears twice (e.g. Vicar Lane ->
        Hyde Park -> Vicar Lane)."""
        out, ptr = [], 0
        for i, n in enumerate(cn):
            for j in range(ptr, len(tps)):
                if tps[j] == n:
                    out.append((j, i))
                    ptr = j + 1
                    break
        return out

    fwd = ordered_match(tp_names)
    bwd = ordered_match(list(reversed(tp_names)))
    if len(fwd) < 2 and len(bwd) < 2:
        return None
    if len(fwd) >= len(bwd):
        anchors = sorted((tp_dist[j], float(offsets[i])) for j, i in fwd)
        rev = False
    else:
        n_tp = len(tp_names)
        anchors = sorted((total - tp_dist[n_tp - 1 - j], float(offsets[i])) for j, i in bwd)
        rev = True
    # drop anchors that would make time non-monotonic along travel
    clean_d, clean_t = [], []
    for d, t in anchors:
        if not clean_t or t >= clean_t[-1]:
            clean_d.append(d)
            clean_t.append(t)
    if len(clean_d) < 2:
        return None
    return clean_d, clean_t, rev


def _color_for(line_id: str) -> str:
    palette = ["6C7A89", "8E6E53", "4B6584", "6B5B95", "588C7E", "B33939",
               "227093", "84817A", "CC8E35", "40739E", "718093", "8C7AE6"]
    return palette[int(hashlib.md5(line_id.encode()).hexdigest(), 16) % len(palette)]


def tram_line_specs(transcriptions_dir: Path, geometry_path: Path) -> list[dict]:
    pages = {p["page_key"]: p for p in load_transcriptions(transcriptions_dir)}
    geom = {r["page_key"]: r for r in json.loads(geometry_path.read_text())["routes"]}
    specs = []
    for key, page in pages.items():
        meta = TRAM_META[key]
        day_tables = [{"day_type": t["day_type"], "direction": d}
                      for t in page["day_tables"] for d in t["directions"]]
        specs.append({
            "line_id": f"T_{meta['short']}", "short_name": meta["short"],
            "long_name": geom[key]["route_name"].title(), "route_type": 0,
            "color": meta["color"], "geometry": geom[key], "day_tables": day_tables,
        })
    return specs


def bus_line_specs(bus_lines_path: Path, geometry_paths: list[Path]) -> tuple[list[dict], list[str]]:
    lines = {l["line_id"]: l for l in json.loads(bus_lines_path.read_text())["lines"]}
    geom = {}
    for p in geometry_paths:
        for r in json.loads(p.read_text())["routes"]:
            geom[r["line_id"]] = r
    specs, skipped = [], []
    for lid, line in sorted(lines.items()):
        if lid not in geom:
            skipped.append(f"{lid}: no geometry")
            continue
        specs.append({
            "line_id": lid, "short_name": line["service_number"],
            "long_name": line["route_names"][0].title(), "route_type": 3,
            "color": _color_for(lid), "geometry": geom[lid],
            "day_tables": line["day_tables"],
        })
    return specs, skipped


def build_feed(specs: list[dict], out_dir: Path,
               era_start: str = "19561001", era_end: str = "19570927",
               time_scale: float = 1.0) -> dict:
    """time_scale > 1 stretches all in-vehicle running times (sensitivity:
    'what if the 1957 timetables were optimistic by X%'); departure patterns
    are unchanged."""
    out_dir.mkdir(parents=True, exist_ok=True)
    registry = StopRegistry()
    routes_rows, trips_rows, stop_times_rows, shapes_rows = [], [], [], []
    summary = {"routes": [], "skipped_directions": []}

    for spec in specs:
        g = spec["geometry"]
        waypoints = [tuple(w) for w in g["waypoints"]]
        cum = cumulative_dist_m(waypoints)
        total = cum[-1]
        tp_names = [canonical_stop(tp["name"]) for tp in g["timing_points"]]
        tp_dist = [project_onto_polyline(waypoints, cum, tp["lat"], tp["lon"])
                   for tp in g["timing_points"]]

        samples = resample_polyline(waypoints, STOP_SPACING_M, anchors_m=tp_dist)
        seq_stop_ids, seq_dists = [], []
        for d, (lat, lon) in samples:
            tp_idx = next((i for i, ad in enumerate(tp_dist) if abs(ad - d) < 1.0), None)
            name = tp_names[tp_idx] if tp_idx is not None else \
                f"{spec['long_name']} (+{int(d)} m)"
            seq_stop_ids.append(registry.get(lat, lon, name, tp_idx is not None))
            seq_dists.append(d)

        route_id = spec["line_id"]
        routes_rows.append({"route_id": route_id, "agency_id": "LCT",
                            "route_short_name": spec["short_name"],
                            "route_long_name": spec["long_name"],
                            "route_type": spec["route_type"],
                            "route_color": spec["color"],
                            "route_text_color": "FFFFFF"})
        shape_id = f"shape_{route_id}"
        for i, (lat, lon) in enumerate(waypoints):
            shapes_rows.append({"shape_id": shape_id, "shape_pt_lat": round(lat, 6),
                                "shape_pt_lon": round(lon, 6), "shape_pt_sequence": i + 1})

        n_trips_route = 0
        trip_counter: dict[tuple, int] = {}
        for table in spec["day_tables"]:
            d = table["direction"]
            services = DAY_TYPE_SERVICES.get(table["day_type"])
            if services is None:
                summary["skipped_directions"].append(
                    f"{route_id}: unknown day_type {table['day_type']}")
                continue
            names = [s["name"] for s in d["stops"]]
            res = _direction_anchors(names, d["stop_offsets_min"], tp_names,
                                     tp_dist, total)
            if res is None:
                summary["skipped_directions"].append(
                    f"{route_id}/{table['day_type']}: stops {names[:4]}... match "
                    f"<2 timing points {tp_names[:4]}...")
                continue
            anchor_d, anchor_t, rev = res
            if time_scale != 1.0:
                anchor_t = [t * time_scale for t in anchor_t]
            dir_stops = list(reversed(seq_stop_ids)) if rev else seq_stop_ids
            dir_dists = [total - x for x in reversed(seq_dists)] if rev else seq_dists

            deps = expand_pattern(d["service_pattern"])
            for service_id in services:
                direction_id = 1 if rev else 0
                for dep_min in deps:
                    n = trip_counter.get((service_id, direction_id), 0)
                    trip_counter[(service_id, direction_id)] = n + 1
                    trip_id = f"{route_id}_{service_id}_{direction_id}_{n:03d}"
                    trips_rows.append({"route_id": route_id, "service_id": service_id,
                                       "trip_id": trip_id, "direction_id": direction_id,
                                       "trip_headsign": names[-1], "shape_id": shape_id})
                    last_t = -1.0
                    for seq, (sid, dist) in enumerate(zip(dir_stops, dir_dists), start=1):
                        t = dep_min + max(_interp_extrap(dist, anchor_d, anchor_t), 0.0)
                        t = max(t, last_t)  # enforce monotonic times
                        last_t = t
                        g_t = _min_to_gtfs(t)
                        stop_times_rows.append({"trip_id": trip_id, "arrival_time": g_t,
                                                "departure_time": g_t, "stop_id": sid,
                                                "stop_sequence": seq})
                    n_trips_route += 1

        summary["routes"].append({"route_id": route_id, "name": spec["long_name"],
                                  "stops_on_route": len(seq_stop_ids),
                                  "trips_all_daytypes": n_trips_route})

    def write(name, fieldnames, rows):
        with open(out_dir / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    write("agency.txt", ["agency_id", "agency_name", "agency_url", "agency_timezone"],
          [{"agency_id": "LCT", "agency_name": "Leeds City Transport (historical reconstruction)",
            "agency_url": "https://en.wikipedia.org/wiki/Leeds_Tramway",
            "agency_timezone": "Europe/London"}])
    write("calendar.txt",
          ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday",
           "saturday", "sunday", "start_date", "end_date"],
          [{"service_id": "weekday", "monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1,
            "friday": 1, "saturday": 0, "sunday": 0, "start_date": era_start, "end_date": era_end},
           {"service_id": "saturday", "monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0,
            "friday": 0, "saturday": 1, "sunday": 0, "start_date": era_start, "end_date": era_end},
           {"service_id": "sunday", "monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0,
            "friday": 0, "saturday": 0, "sunday": 1, "start_date": era_start, "end_date": era_end}])
    write("routes.txt", ["route_id", "agency_id", "route_short_name", "route_long_name",
                         "route_type", "route_color", "route_text_color"], routes_rows)
    write("stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon"],
          [{"stop_id": s["id"], "stop_name": s["name"], "stop_lat": round(s["lat"], 6),
            "stop_lon": round(s["lon"], 6)} for s in registry.stops])
    write("trips.txt", ["route_id", "service_id", "trip_id", "direction_id",
                        "trip_headsign", "shape_id"], trips_rows)
    write("stop_times.txt", ["trip_id", "arrival_time", "departure_time", "stop_id",
                             "stop_sequence"], stop_times_rows)
    write("shapes.txt", ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"],
          shapes_rows)

    summary["total_stops"] = len(registry.stops)
    summary["total_trips"] = len(trips_rows)
    summary["total_stop_times"] = len(stop_times_rows)
    (out_dir / "build_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def build(transcriptions_dir: Path, geometry_path: Path, out_dir: Path,
          era_start: str = "19561001", era_end: str = "19570927") -> dict:
    """Trams-only feed (back-compat entry point)."""
    specs = tram_line_specs(transcriptions_dir, geometry_path)
    return build_feed(specs, out_dir, era_start, era_end)
