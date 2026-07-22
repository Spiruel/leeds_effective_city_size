#!/usr/bin/env python3
"""Blog figures beyond the headline curve: corridor time-difference map and
isochrone comparison maps. Reads analysis/ outputs."""

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import contextily as cx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from leeds_trams import ANALYSIS, CENTRE_LAT, CENTRE_LON, PROJECT_ROOT

# Tram route shapes
shape_pts = {}
with open(PROJECT_ROOT / "gtfs_historical" / "shapes.txt") as f:
    for row in csv.DictReader(f):
        shape_pts.setdefault(row["shape_id"], []).append(
            (int(row["shape_pt_sequence"]), float(row["shape_pt_lat"]), float(row["shape_pt_lon"])))

rows = list(csv.DictReader(open(ANALYSIS / "lsoa_times.csv")))

# 1950s tram stops, for the same corridor definition as stats.json
from leeds_trams.geometry import GridIndex  # noqa: E402

stop_grid = GridIndex(800)
with open(PROJECT_ROOT / "gtfs_historical" / "stops.txt") as f:
    for row in csv.DictReader(f):
        stop_grid.add(float(row["stop_lat"]), float(row["stop_lon"]))


def draw_routes(ax, color="#333", lw=1.6, alpha=0.9):
    for pts in shape_pts.values():
        pts = sorted(pts)
        ax.plot([p[2] for p in pts], [p[1] for p in pts], color=color, lw=lw,
                alpha=alpha, zorder=3)


# ── Figure 1: corridor time difference ────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 9))
lats = np.array([float(r["lat"]) for r in rows])
lons = np.array([float(r["lon"]) for r in rows])
tth = np.array([float(r["tt_tram_1950s_min"]) for r in rows])
ttm = np.array([float(r["tt_modern_min"]) for r in rows])
pop = np.array([float(r["population"]) for r in rows])
# corridor = within 800 m of a 1950s tram stop (same definition as stats.json)
mask = np.array([any(True for _ in stop_grid.near(la, lo, 800))
                 for la, lo in zip(lats, lons)])
diff = ttm - tth
sc = ax.scatter(lons[mask], lats[mask], c=np.clip(diff[mask], -15, 15),
                s=pop[mask] / 40, cmap="RdBu_r", vmin=-15, vmax=15,
                edgecolors="k", linewidths=0.3, zorder=4)
draw_routes(ax, color="#222", lw=1.2, alpha=0.8)
ax.plot(CENTRE_LON, CENTRE_LAT, "ro", mec="w", ms=10, zorder=6)
ax.set_xlim(-1.62, -1.42)
ax.set_ylim(53.72, 53.87)
cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.OpenStreetMap.Mapnik)
ax.set_xticks([]), ax.set_yticks([])
cb = fig.colorbar(sc, ax=ax, shrink=0.7, label="Minutes slower today (red) / faster today (blue)")
ax.set_title("Getting to Briggate: 2026 bus vs 1957 tram, by neighbourhood\n"
             "(LSOAs the tram network served; dot size = population; lines = tram routes)")
fig.tight_layout()
fig.savefig(ANALYSIS / "corridor_map.png", dpi=150)
print("corridor_map.png")

# ── Figure 2: 20/30 min isochrones, both eras ─────────────────────────────
iso = json.loads((ANALYSIS / "isochrones.geojson").read_text())
fig, ax = plt.subplots(figsize=(10, 10))

# Shades of Yellow (1957) and Purple (modern)
STYLE = {
    ("tram_1950s", 20): ("#FFD700", 0.6), # Gold
    ("tram_1950s", 30): ("#FFA500", 0.4), # Orange
    ("modern", 20): ("#9370DB", 0.6),     # MediumPurple
    ("modern", 30): ("#4B0082", 0.4),     # Indigo
}

for threshold in [30, 20]:  # Largest first
    for f in iso["features"]:
        era = f["properties"]["era"]
        t = f["properties"]["threshold_min"]
        if (era, t) not in STYLE: continue
        if era == "full_1957": continue
        
        color, alpha = STYLE[(era, t)]
        for poly in f["geometry"]["coordinates"]:
            for ring_i, ring in enumerate(poly):
                xs = [c[0] for c in ring]
                ys = [c[1] for c in ring]
                #if ring_i == 0:
                #    ax.fill(xs, ys, color=color, alpha=0.3, zorder=2)
                ax.plot(xs, ys, color=color, lw=2.5, alpha=0.9, zorder=3)

draw_routes(ax, color="#222", lw=1.2, alpha=0.6)
ax.plot(CENTRE_LON, CENTRE_LAT, "ro", mec="w", ms=10, zorder=6)

from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='#FFD700', edgecolor='#FFA500', label='1957 Trams (20/30 min)'),
    Patch(facecolor='#9370DB', edgecolor='#4B0082', label='2026 Buses (20/30 min)'),
]
ax.legend(handles=legend_elements, loc="upper left")

ax.set_xlim(-1.70, -1.40)
ax.set_ylim(53.70, 53.88)
cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.OpenStreetMap.Mapnik)
ax.set_xticks([]), ax.set_yticks([])
ax.set_title("Reach within 20 and 30 minutes from Briggate\n1957 trams (yellow) vs 2026 buses (purple)")
fig.tight_layout()
fig.savefig(ANALYSIS / "isochrones_30min.png", dpi=150)
print("isochrones_30min.png (Yellow/Purple)")

# Everything below needs the full 1957 network analysis
stats = json.loads((ANALYSIS / "stats.json").read_text())
if "full_1957" not in stats["eras"]:
    print("full_1957 era not in stats.json - stopping after base figures")
    raise SystemExit

tth_full = np.array([float(r["tt_full_1957_min"]) for r in rows])

# ── Figure 3: 20/30 min isochrones, FULL 1957 network vs 2026 ────────────────
fig, ax = plt.subplots(figsize=(10, 10))

STYLE3 = {
    ("full_1957", 20): ("#FFD700", 0.6),
    ("full_1957", 30): ("#FFA500", 0.4),
    ("modern", 20): ("#9370DB", 0.6),
    ("modern", 30): ("#4B0082", 0.4),
}

for threshold in [30, 20]:
    for f in iso["features"]:
        era = f["properties"]["era"]
        t = f["properties"]["threshold_min"]
        if (era, t) not in STYLE3: continue
        
        color, alpha = STYLE3[(era, t)]
        for poly in f["geometry"]["coordinates"]:
            for ring_i, ring in enumerate(poly):
                xs = [c[0] for c in ring]
                ys = [c[1] for c in ring]
                #if ring_i == 0:
                #    ax.fill(xs, ys, color=color, alpha=0.3, zorder=2)
                ax.plot(xs, ys, color=color, lw=2.0, alpha=0.9, zorder=3)

draw_routes(ax, color="#222", lw=1.0, alpha=0.4)
ax.plot(CENTRE_LON, CENTRE_LAT, "ro", mec="w", ms=10, zorder=6)

legend_elements3 = [
    Patch(facecolor='#FFD700', edgecolor='#FFA500', label='1957 Full Network (20/30 min)'),
    Patch(facecolor='#9370DB', edgecolor='#4B0082', label='2026 Buses (20/30 min)'),
]
ax.legend(handles=legend_elements3, loc="upper left")

ax.set_xlim(-1.75, -1.35)
ax.set_ylim(53.68, 53.90)
cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.OpenStreetMap.Mapnik)
ax.set_xticks([]), ax.set_yticks([])
ax.set_title("Reach within 20 and 30 minutes from Briggate\n1957 full network (yellow) vs 2026 buses (purple)")
fig.tight_layout()
fig.savefig(ANALYSIS / "isochrones_30min_full.png", dpi=150)
print("isochrones_30min_full.png (Yellow/Purple)")



# ── Figure 4: then-vs-now scatter, one dot per LSOA ───────────────────────
fig, ax = plt.subplots(figsize=(8, 8))
ttm = np.array([float(r["tt_modern_min"]) for r in rows])
pop = np.array([float(r["population"]) for r in rows])
m = (tth_full <= 60) & (ttm <= 90)
ax.scatter(tth_full[m], ttm[m], s=pop[m] / 60, c=np.clip(ttm[m] - tth_full[m], -15, 15),
           cmap="RdBu_r", vmin=-15, vmax=15, edgecolors="k", linewidths=0.2, alpha=0.85)
lim = [0, 75]
ax.plot(lim, lim, "k--", lw=1)
ax.annotate("slower today", xy=(18, 48), color="#922", fontsize=13)
ax.annotate("faster today", xy=(48, 18), color="#226", fontsize=13)
ax.set_xlim(lim), ax.set_ylim(lim)
ax.set_xlabel("Minutes to Briggate, 1957 network (trams + buses)")
ax.set_ylabel("Minutes to Briggate, 2026 network (buses)")
ax.set_title("Every Leeds neighbourhood, then vs now\n(dot size = population; above the line = worse today)")
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(ANALYSIS / "scatter_then_now.png", dpi=150)
print("scatter_then_now.png")

# ── Figure 5: effective city size bars ────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5.5))
bars = [("Walking only", stats["walk_only_curve"]["30"], "#7F8C8D"),
        ("1957 trams only", stats["eras"]["tram_1950s"]["population_curve"]["30"], "#E67E22"),
        ("1957 full network", stats["eras"]["full_1957"]["population_curve"]["30"], "#C0392B"),
        ("2026 buses", stats["eras"]["modern"]["population_curve"]["30"], "#2980B9")]
ext_path = ANALYSIS / "extended_stats.json"
if ext_path.exists():
    ext = json.loads(ext_path.read_text())
    if "rail" in ext:
        bars.insert(3, ("1957 network + BR rail",
                        ext["rail"]["full_1957_with_rail_curve"]["30"], "#922B21"))
        bars.append(("2026 buses + rail",
                     ext["rail"]["modern_with_rail_curve"]["30"], "#1F618D"))
    if "car" in ext:
        bars.append(("2026 car (peak + parking)", ext["car"]["curve"]["30"], "#333333"))
names = [b[0] for b in bars]
vals = [b[1] / 1e3 for b in bars]
cols = [b[2] for b in bars]
ax.barh(names, vals, color=cols)
for i, v in enumerate(vals):
    ax.text(v + 5, i, f"{v:,.0f}k", va="center")
ax.set_xlabel("People within 30 minutes of Briggate (thousands, 2021 census)")
ax.set_title("The effective size of Leeds, 1957 vs 2026")
ax.set_xlim(0, max(vals) * 1.18)
fig.tight_layout()
fig.savefig(ANALYSIS / "effective_size.png", dpi=150)
print("effective_size.png")

# ── Table: departures toward town, 07:30-09:00, key suburbs then vs now ───
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from leeds_trams import DATA
from leeds_trams.geometry import haversine_m
from leeds_trams.router import Feed, _gtfs_time_to_min
import csv as _csv

SUBURBS = {"Middleton": (53.7484, -1.5415), "Belle Isle": (53.7713, -1.5378),
           "Moortown": (53.8395, -1.5305), "Harehills": (53.8105, -1.5084),
           "Bramley": (53.8100, -1.6350), "Headingley (North Lane)": (53.8196, -1.5779),
           "Pudsey": (53.7975, -1.6630), "Seacroft": (53.8210, -1.4585)}


def departures_near(feed, lat, lon, radius_m=500):
    """Count vehicle departures 07:30-09:00 at stops within radius."""
    stops = {s for s, _ in feed.stops_near(lat, lon, radius_m)}
    n = 0
    for pid, seq in enumerate(feed.pattern_stops):
        positions = [i for i, s in enumerate(seq) if s in stops]
        if not positions:
            continue
        pos = positions[0]
        dep = feed.pattern_dep[pid]
        n += int(((dep[:, pos] >= 450) & (dep[:, pos] < 540)).sum())
    return n


feed_1957 = Feed(PROJECT_ROOT / "gtfs_historical_full", service_id="weekday")
feed_2026 = Feed(DATA / "modern" / "filtered")
freq_rows = [["suburb", "deps_1957_full", "deps_2026"]]
for name, (la, lo) in SUBURBS.items():
    n57 = departures_near(feed_1957, la, lo)
    n26 = departures_near(feed_2026, la, lo)
    freq_rows.append([name, n57, n26])
    print(f"  {name:24s} 1957: {n57:4d}   2026: {n26:4d}  (deps 07:30-09:00 within 500 m)")
with open(ANALYSIS / "suburb_frequencies.csv", "w", newline="") as f:
    _csv.writer(f).writerows(freq_rows)
print("suburb_frequencies.csv")
