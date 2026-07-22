"""Build a minimal GTFS dir from a frequency-based rail spec, and merge GTFS
dirs. Both eras' rail is specified the same way (stations, run times, peak /
off-peak headways), so the rail treatment is methodologically symmetric.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

PEAKS = [(7 * 60, 9 * 60 + 30), (16 * 60, 18 * 60 + 30)]


def _hhmm(m: float) -> str:
    s = int(round(m * 60))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _expand(first: str, last: str, peak: float, offpeak: float) -> list[float]:
    h, m = first.split(":")
    t = int(h) * 60 + int(m)
    h, m = last.split(":")
    end = int(h) * 60 + int(m)
    deps = []
    while t <= end:
        deps.append(t)
        t += peak if any(a <= t < b for a, b in PEAKS) else offpeak
    return deps


def build_rail_gtfs(spec_path: Path, out_dir: Path, prefix: str) -> dict:
    spec = json.loads(spec_path.read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    coords = {s["name"]: (s["lat"], s["lon"]) for s in spec["stations"]}

    stops, trips, stop_times = {}, [], []
    for si, svc in enumerate(spec["services"]):
        route_id = f"{prefix}R{si:02d}"
        names = svc["stations"]
        runs = svc["run_times_min"]
        for name in names:
            sid = f"{prefix}S_" + name.replace(" ", "_")
            stops[sid] = (name, *coords[name])
        deps = _expand(svc["first"], svc["last"],
                       svc["headway_min_peak"], svc["headway_min_offpeak"])
        for direction in (0, 1):
            seq_names = names if direction == 0 else list(reversed(names))
            seq_runs = runs if direction == 0 else [runs[-1] - r for r in reversed(runs)]
            for n, dep in enumerate(deps):
                trip_id = f"{route_id}_{direction}_{n:03d}"
                trips.append({"route_id": route_id, "service_id": "weekday",
                              "trip_id": trip_id})
                for seq, (name, r) in enumerate(zip(seq_names, seq_runs), start=1):
                    t = _hhmm(dep + r)
                    stop_times.append({"trip_id": trip_id, "arrival_time": t,
                                       "departure_time": t,
                                       "stop_id": f"{prefix}S_" + name.replace(" ", "_"),
                                       "stop_sequence": seq})

    with open(out_dir / "stops.txt", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stop_id", "stop_name", "stop_lat", "stop_lon"])
        for sid, (name, lat, lon) in stops.items():
            w.writerow([sid, name, lat, lon])
    with open(out_dir / "trips.txt", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["route_id", "service_id", "trip_id"])
        w.writeheader()
        w.writerows(trips)
    with open(out_dir / "stop_times.txt", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["trip_id", "arrival_time", "departure_time",
                                          "stop_id", "stop_sequence"])
        w.writeheader()
        w.writerows(stop_times)
    return {"stations": len(stops), "services": len(spec["services"]),
            "trips": len(trips)}


def merge_gtfs_dirs(dirs: list[Path], out_dir: Path) -> None:
    """Concatenate minimal GTFS dirs (stop ids must already be unique)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    plans = {
        "stops.txt": ["stop_id", "stop_name", "stop_lat", "stop_lon"],
        "trips.txt": ["route_id", "service_id", "trip_id"],
        "stop_times.txt": ["trip_id", "arrival_time", "departure_time",
                           "stop_id", "stop_sequence"],
    }
    for fname, cols in plans.items():
        with open(out_dir / fname, "w", newline="") as out_f:
            w = csv.DictWriter(out_f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for d in dirs:
                src = d / fname
                if not src.exists():
                    continue
                with open(src) as f:
                    for row in csv.DictReader(f):
                        row.setdefault("service_id", "weekday")
                        w.writerow(row)
