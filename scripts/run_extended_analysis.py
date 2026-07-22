#!/usr/bin/env python3
"""Extended analyses answering the critique of the base comparison:

  - rail added to BOTH eras (symmetric frequency-spec feeds)
  - jobs-weighted accessibility (BRES workplace employment)
  - car layer (OSRM free-flow + documented peak/parking adjustments)
  - sensitivity: 1957 speed haircuts, alternative origins, walking params

Writes analysis/extended_stats.json. Skips any section whose input data is
missing (agents may still be fetching it). `--mini KMH DETOUR` is an internal
mode used for the walking sensitivity (re-imports with env overrides).
"""

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leeds_trams import CENTRE_LAT, CENTRE_LON, DATA, ANALYSIS, PROJECT_ROOT
from leeds_trams.accessibility import (centroid_travel_times, load_centroids,
                                       population_curve, stop_travel_times)
from leeds_trams.router import Feed

DEP_TIMES = [480, 490, 500]
FULL = PROJECT_ROOT / "gtfs_historical_full"
MODERN = DATA / "modern" / "filtered"

centroids = load_centroids(DATA / "population" / "leeds_lsoa_population.csv")


def era_curves(gtfs_dir, service_id, origin=(CENTRE_LAT, CENTRE_LON), weights=None):
    feed = Feed(gtfs_dir, service_id=service_id)
    tt = stop_travel_times(feed, DEP_TIMES, origin=origin)
    cen = centroid_travel_times(feed, tt, centroids, origin=origin)
    if weights is None:
        return population_curve(cen, centroids), cen
    import numpy as np
    w = np.array([weights.get(c["code"], 0.0) for c in centroids])
    return {t: float(w[cen <= t].sum()) for t in (15, 30, 45, 60)}, cen


if len(sys.argv) > 2 and sys.argv[1] == "--mini":
    # internal: pop within 30/45 for both eras under env-overridden walk params
    out = {}
    for name, gdir, sid in [("full_1957", FULL, "weekday"), ("modern", MODERN, None)]:
        curve, _ = era_curves(gdir, sid)
        out[name] = {"30": curve[30], "45": curve[45]}
    print(json.dumps(out))
    sys.exit(0)

ext: dict = {}

# ── 1. Rail, both eras ─────────────────────────────────────────────────────
from leeds_trams.rail_gtfs import build_rail_gtfs, merge_gtfs_dirs

rail_specs = {"1957": DATA / "historical" / "rail_1957.json",
              "2026": DATA / "modern" / "rail_2026.json"}
if all(p.exists() for p in rail_specs.values()):
    r57 = build_rail_gtfs(rail_specs["1957"], PROJECT_ROOT / "gtfs_rail_1957", "H")
    r26 = build_rail_gtfs(rail_specs["2026"], PROJECT_ROOT / "gtfs_rail_2026", "M")
    merge_gtfs_dirs([FULL, PROJECT_ROOT / "gtfs_rail_1957"],
                    PROJECT_ROOT / "gtfs_1957_with_rail")
    merge_gtfs_dirs([MODERN, PROJECT_ROOT / "gtfs_rail_2026"],
                    DATA / "modern" / "filtered_with_rail")
    c57, _ = era_curves(PROJECT_ROOT / "gtfs_1957_with_rail", "weekday")
    c26, _ = era_curves(DATA / "modern" / "filtered_with_rail", None)
    ext["rail"] = {"spec_1957": r57, "spec_2026": r26,
                   "full_1957_with_rail_curve": c57,
                   "modern_with_rail_curve": c26}
    print("rail:", {k: c57[k] for k in (30, 45)}, "vs modern",
          {k: c26[k] for k in (30, 45)})
else:
    print("rail specs not ready - skipped")

# ── 2. Jobs-weighted ───────────────────────────────────────────────────────
jobs_csv = DATA / "population" / "leeds_lsoa_jobs.csv"
if jobs_csv.exists():
    jobs = {r["code"]: float(r["jobs"]) for r in csv.DictReader(open(jobs_csv))}
    jw = {}
    for name, gdir, sid in [("full_1957", FULL, "weekday"), ("modern", MODERN, None)]:
        if (PROJECT_ROOT / "gtfs_1957_with_rail" / "stops.txt").exists():
            gdir = {"full_1957": PROJECT_ROOT / "gtfs_1957_with_rail",
                    "modern": DATA / "modern" / "filtered_with_rail"}[name]
        curve, _ = era_curves(gdir, sid, weights=jobs)
        jw[name] = curve
    ext["jobs_weighted"] = {"source": "see data/population/jobs_README.md",
                            "total_jobs": sum(jobs.values()), "curves": jw}
    print("jobs-weighted (jobs within 30 min):",
          {k: int(v[30]) for k, v in jw.items()})
else:
    print("jobs csv not ready - skipped")

# ── 3. Car layer ───────────────────────────────────────────────────────────
car_csv = ANALYSIS / "car_times.csv"
if car_csv.exists():
    import numpy as np
    ff = {r["code"]: float(r["freeflow_min"]) for r in csv.DictReader(open(car_csv))
          if r.get("freeflow_min")}
    PEAK_MULT, PARK_MIN = 1.4, 8.0   # documented in analysis/car_README.md
    pops = np.array([c["pop"] for c in centroids])
    adj = np.array([ff.get(c["code"], np.inf) * PEAK_MULT + PARK_MIN
                    for c in centroids])
    ext["car"] = {"peak_multiplier": PEAK_MULT, "parking_penalty_min": PARK_MIN,
                  "curve": {t: float(pops[adj <= t].sum()) for t in (15, 30, 45, 60)},
                  "freeflow_curve": {t: float(pops[np.array(
                      [ff.get(c["code"], np.inf) for c in centroids]) <= t].sum())
                      for t in (15, 30, 45, 60)}}
    print("car (adjusted):", ext["car"]["curve"])
else:
    print("car_times.csv not ready - skipped")

# ── 4. Speed-haircut sensitivity (1957 timetable optimism test) ────────────
from leeds_trams.historical_gtfs import build_feed, bus_line_specs, tram_line_specs

trams = tram_line_specs(DATA / "transcriptions", DATA / "historical" / "route_geometry.json")
buses, _ = bus_line_specs(DATA / "historical" / "bus_lines.json",
                          sorted((DATA / "historical").glob("bus_route_geometry_*.json")))
ext["haircut"] = {}
for label, scale in [("minus10pct", 1.111), ("minus20pct", 1.25)]:
    with tempfile.TemporaryDirectory() as td:
        build_feed(trams + buses, Path(td), time_scale=scale)
        curve, _ = era_curves(Path(td), "weekday")
        ext["haircut"][label] = {"time_scale": scale, "pop30": curve[30], "pop45": curve[45]}
        print(f"haircut {label}: pop30 {curve[30]/1000:.0f}k")

# ── 5. Alternative origins ─────────────────────────────────────────────────
ORIGINS = {"city_square": (53.7959, -1.5468), "st_james_hospital": (53.8076, -1.5210)}
ext["origins"] = {}
for oname, origin in ORIGINS.items():
    row = {}
    for name, gdir, sid in [("full_1957", FULL, "weekday"), ("modern", MODERN, None)]:
        curve, _ = era_curves(gdir, sid, origin=origin)
        row[name] = {"pop30": curve[30], "pop45": curve[45]}
    ext["origins"][oname] = row
    print(f"origin {oname}: 1957 {row['full_1957']['pop30']/1000:.0f}k "
          f"vs 2026 {row['modern']['pop30']/1000:.0f}k")

# ── 6. Walking-parameter sensitivity (subprocess with env overrides) ───────
ext["walk_sensitivity"] = {}
for label, kmh, detour in [("slow_4.0kmh", "4.0", "1.3"), ("fast_5.6kmh", "5.6", "1.3"),
                           ("detour_1.5", "4.8", "1.5")]:
    env = dict(os.environ, LT_WALK_KMH=kmh, LT_DETOUR=detour)
    out = subprocess.run([sys.executable, __file__, "--mini", kmh, detour],
                         env=env, capture_output=True, text=True, timeout=1200)
    ext["walk_sensitivity"][label] = json.loads(out.stdout.strip().splitlines()[-1])
    print(f"walk {label}: {ext['walk_sensitivity'][label]}")

(ANALYSIS / "extended_stats.json").write_text(json.dumps(ext, indent=2))
print(f"\nWrote {ANALYSIS}/extended_stats.json")
