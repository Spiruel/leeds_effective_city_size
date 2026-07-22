#!/usr/bin/env python3
"""Run the past-vs-present accessibility analysis Leeds, 1950s trams vs today's buses).

Outputs:
  analysis/stats.json          - headline numbers
  analysis/isochrones.geojson  - 15/30/45-min isochrones, both eras
  analysis/curve.png           - population reachable vs travel-time curve
  analysis/lsoa_times.csv      - per-LSOA door-to-door times, both eras
  webapp/data.json             - map payload for the webapp
"""

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leeds_trams import (ANALYSIS, CENTRE_LAT, CENTRE_LON, DATA,
                         EFFECTIVE_WALK_M_MIN, PROJECT_ROOT)
from leeds_trams.accessibility import (THRESHOLDS, analyse_era, load_centroids,
                                       population_curve)
from leeds_trams.geometry import haversine_m

DEP_TIMES = [8 * 60, 8 * 60 + 10, 8 * 60 + 20]   # 08:00/08:10/08:20 departures
ISO_THRESHOLDS = (10, 20, 30, 40, 50, 60)

ANALYSIS.mkdir(exist_ok=True)
centroids = load_centroids(DATA / "population" / "leeds_lsoa_population.csv")
total_pop = sum(c["pop"] for c in centroids)
print(f"{len(centroids)} LSOA centroids, total population {total_pop:,.0f}")

print("\n=== 1957 trams only ===")
hist = analyse_era(PROJECT_ROOT / "gtfs_historical", "weekday", centroids,
                   DEP_TIMES, ISO_THRESHOLDS)
print(f"stops={hist['n_stops']} trips={hist['n_trips']} patterns={hist['n_patterns']}")

eras = [("tram_1950s", hist)]
full = None
if (PROJECT_ROOT / "gtfs_historical_full" / "stop_times.txt").exists():
    print("\n=== 1957 full network (trams + buses) ===")
    full = analyse_era(PROJECT_ROOT / "gtfs_historical_full", "weekday", centroids,
                       DEP_TIMES, ISO_THRESHOLDS)
    print(f"stops={full['n_stops']} trips={full['n_trips']} patterns={full['n_patterns']}")
    eras.append(("full_1957", full))

print("\n=== Modern network (BODS) ===")
mod = analyse_era(DATA / "modern" / "filtered", None, centroids,
                  DEP_TIMES, ISO_THRESHOLDS)
print(f"stops={mod['n_stops']} trips={mod['n_trips']} patterns={mod['n_patterns']}")
eras.append(("modern", mod))

# Walk-only baseline
walk_tt = np.array([haversine_m(CENTRE_LAT, CENTRE_LON, c["lat"], c["lon"])
                    for c in centroids]) / EFFECTIVE_WALK_M_MIN
walk_curve = population_curve(walk_tt, centroids)

stats = {
    "method": {
        "origin": {"lat": CENTRE_LAT, "lon": CENTRE_LON, "name": "Briggate, Leeds"},
        "departures": ["08:00", "08:10", "08:20 (averaged)"],
        "walking": "4.8 km/h, crow-fly x1.3, max 20 min access/egress walk",
        "router": "RAPTOR, unlimited transfers (1 min boarding penalty after first ride)",
        "population": "Census 2021 LSOA population-weighted centroids within 30 km",
        "modern_service_date": json.loads((DATA / "modern" / "filtered" / "filter_stats.json").read_text())["service_date"],
    },
    "total_population_30km": total_pop,
    "eras": {},
    "walk_only_curve": walk_curve,
}
for era_name, era in eras:
    stats["eras"][era_name] = {
        "n_stops": era["n_stops"], "n_trips": era["n_trips"],
        "stops_reachable_30min": era["stops_reachable_30min"],
        "population_curve": era["population_curve"],
        "isochrone_area_km2": era["isochrone_area_km2"],
    }

# Like-for-like corridor comparison: LSOAs whose centroid is within 800 m of a
# 1950s tram stop - i.e. the places the trams actually served.
hist_feed = hist["feed"]
corridor_idx = []
for i, c in enumerate(centroids):
    if any(True for _ in hist_feed.stops_near(c["lat"], c["lon"], 800)):
        corridor_idx.append(i)
ci = np.array(corridor_idx)
cpop = np.array([centroids[i]["pop"] for i in ci])
tt_h, tt_m = hist["centroid_tt"][ci], mod["centroid_tt"][ci]
stats["corridor_comparison"] = {
    "definition": "LSOA centroids within 800 m of a 1950s tram stop",
    "n_lsoas": len(ci),
    "population": float(cpop.sum()),
    "mean_tt_tram_1950s_min": round(float(np.average(tt_h, weights=cpop)), 1),
    "mean_tt_modern_min": round(float(np.average(tt_m, weights=cpop)), 1),
    "median_tt_tram_1950s_min": round(float(np.median(tt_h)), 1),
    "median_tt_modern_min": round(float(np.median(tt_m)), 1),
    "pop_within_30_tram_1950s": float(cpop[tt_h <= 30].sum()),
    "pop_within_30_modern": float(cpop[tt_m <= 30].sum()),
    "pop_faster_by_tram": float(cpop[tt_h < tt_m - 2].sum()),
    "pop_faster_by_modern": float(cpop[tt_m < tt_h - 2].sum()),
    "pop_about_the_same": float(cpop[np.abs(tt_h - tt_m) <= 2].sum()),
}
print("\nCorridor comparison:", json.dumps(stats["corridor_comparison"], indent=2))

# Full-network 1957 vs modern
# every LSOA within 800 m of ANY 1957 stop (tram or bus)
if full is not None:
    full_feed = full["feed"]
    fi = np.array([i for i, c in enumerate(centroids)
                   if any(True for _ in full_feed.stops_near(c["lat"], c["lon"], 800))])
    fpop = np.array([centroids[i]["pop"] for i in fi])
    tt_f, tt_m2 = full["centroid_tt"][fi], mod["centroid_tt"][fi]
    stats["full_network_comparison"] = {
        "definition": "LSOA centroids within 800 m of any 1957 stop (tram or bus)",
        "n_lsoas": len(fi),
        "population": float(fpop.sum()),
        "mean_tt_full_1957_min": round(float(np.average(tt_f, weights=fpop)), 1),
        "mean_tt_modern_min": round(float(np.average(tt_m2, weights=fpop)), 1),
        "pop_within_30_full_1957": float(fpop[tt_f <= 30].sum()),
        "pop_within_30_modern": float(fpop[tt_m2 <= 30].sum()),
        "pop_faster_in_1957": float(fpop[tt_f < tt_m2 - 2].sum()),
        "pop_faster_now": float(fpop[tt_m2 < tt_f - 2].sum()),
        "pop_about_the_same": float(fpop[np.abs(tt_f - tt_m2) <= 2].sum()),
    }
    print("\nFull-network comparison:", json.dumps(stats["full_network_comparison"], indent=2))

(ANALYSIS / "stats.json").write_text(json.dumps(stats, indent=2))
print("\n", json.dumps({k: v for k, v in stats["eras"].items()}, indent=2)[:2000])

# Per-LSOA table
with open(ANALYSIS / "lsoa_times.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["code", "name", "lat", "lon", "population", "tt_tram_1950s_min",
                "tt_full_1957_min", "tt_modern_min", "tt_walk_min"])
    for i, c in enumerate(centroids):
        w.writerow([c["code"], c["name"], c["lat"], c["lon"], int(c["pop"]),
                    round(float(hist["centroid_tt"][i]), 1),
                    round(float(full["centroid_tt"][i]), 1) if full is not None else "",
                    round(float(mod["centroid_tt"][i]), 1),
                    round(float(walk_tt[i]), 1)])

# Isochrone GeoJSON (all eras)
features = []
for era_name, era in eras:
    for t, gj in era["isochrones"].items():
        features.append({"type": "Feature", "geometry": gj,
                         "properties": {"era": era_name, "threshold_min": t,
                                        "area_km2": era["isochrone_area_km2"][t]}})
(ANALYSIS / "isochrones.geojson").write_text(
    json.dumps({"type": "FeatureCollection", "features": features}))

# Chart: cumulative population vs time
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(9, 6))
xs = THRESHOLDS
ax.plot(xs, [hist["population_curve"][t] / 1e3 for t in xs], "o-",
        color="#C0392B", label="1957: trams only (+ walking)")
if full is not None:
    ax.plot(xs, [full["population_curve"][t] / 1e3 for t in xs], "^-",
            color="#7B241C", label="1957: full network, trams + buses (+ walking)")
ax.plot(xs, [mod["population_curve"][t] / 1e3 for t in xs], "s-",
        color="#2980B9", label="2026: buses (+ walking)")
ax.plot(xs, [walk_curve[t] / 1e3 for t in xs], "--", color="#7F8C8D",
        label="Walking only")
ax.set_xlabel("Door-to-door travel time from Briggate (minutes)")
ax.set_ylabel("Population reachable (thousands, 2021 census)")
ax.set_title("How many people can reach Leeds city centre?\n1957 network vs today's buses (same walking model, same population)")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(ANALYSIS / "curve.png", dpi=150)
print(f"\nWrote {ANALYSIS}/stats.json, lsoa_times.csv, isochrones.geojson, curve.png")

# Webapp payload
hist_routes = []
with open(PROJECT_ROOT / "gtfs_historical" / "shapes.txt") as f:
    shape_pts = {}
    for row in csv.DictReader(f):
        shape_pts.setdefault(row["shape_id"], []).append(
            (int(row["shape_pt_sequence"]), float(row["shape_pt_lat"]), float(row["shape_pt_lon"])))
with open(PROJECT_ROOT / "gtfs_historical" / "routes.txt") as f:
    for row in csv.DictReader(f):
        pts = sorted(shape_pts[f"shape_{row['route_id']}"])
        hist_routes.append({"type": "Feature",
                            "geometry": {"type": "LineString",
                                         "coordinates": [[lon, lat] for _, lat, lon in pts]},
                            "properties": {"id": row["route_id"],
                                           "name": row["route_long_name"],
                                           "color": "#" + row["route_color"]}})

webapp = {
    "meta": {"centre_lat": CENTRE_LAT, "centre_lon": CENTRE_LON,
             "generated": "scripts/run_analysis.py"},
    "stats": stats,
    "tram_routes": {"type": "FeatureCollection", "features": hist_routes},
    "isochrones": {"type": "FeatureCollection", "features": features},
}
(PROJECT_ROOT / "webapp" / "data.json").write_text(json.dumps(webapp))
print(f"Wrote webapp/data.json")
