#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import contextily as cx
from matplotlib.patches import Patch
import csv

# Setup paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from leeds_trams import ANALYSIS, CENTRE_LAT, CENTRE_LON, PROJECT_ROOT
PUBLISH_DIR = ANALYSIS / "publish"
PUBLISH_DIR.mkdir(exist_ok=True)

# Data journalism style
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "axes.titlesize": 16,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.labelsize": 12,
    "axes.labelcolor": "#333333",
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "xtick.color": "#555555",
    "ytick.color": "#555555",
    "text.color": "#222222",
    "axes.edgecolor": "#CCCCCC",
    "axes.linewidth": 1.0,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "grid.color": "#E5E5E5",
    "grid.linewidth": 0.5,
    "grid.alpha": 1.0,
    "figure.facecolor": "#FFFFFF",
    "axes.facecolor": "#FFFFFF",
    "figure.figsize": (9, 6),
    "figure.autolayout": True
})

BRAND_ORANGE = "#E65100"  # 1957 full network
BRAND_BLUE = "#0277BD"    # 2026 buses
BRAND_GRAY = "#9E9E9E"    # Others

def add_title_subtitle(ax, title, subtitle, pad=40):
    ax.set_title(title, pad=pad, loc='left')
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, color='#555555', fontsize=12, ha='left')

# Load data
stats = json.loads((ANALYSIS / "stats.json").read_text())
rows = list(csv.DictReader(open(ANALYSIS / "lsoa_times.csv")))
iso = json.loads((ANALYSIS / "isochrones.geojson").read_text())

# Tram route shapes
shape_pts = {}
with open(PROJECT_ROOT / "gtfs_historical" / "shapes.txt") as f:
    for row in csv.DictReader(f):
        shape_pts.setdefault(row["shape_id"], []).append(
            (int(row["shape_pt_sequence"]), float(row["shape_pt_lat"]), float(row["shape_pt_lon"])))

def draw_routes(ax, color="#333", lw=1.6, alpha=0.9):
    for pts in shape_pts.values():
        pts = sorted(pts)
        ax.plot([p[2] for p in pts], [p[1] for p in pts], color=color, lw=lw,
                alpha=alpha, zorder=2)

# ── 1. Effective City Size Bar Chart ───
fig, ax = plt.subplots(figsize=(10, 6))

bars = [
    ("Walking only", stats["walk_only_curve"]["30"], BRAND_GRAY),
    ("2026 buses", stats["eras"]["modern"]["population_curve"]["30"], BRAND_BLUE),
    ("1957 trams only", stats["eras"]["tram_1950s"]["population_curve"]["30"], BRAND_GRAY),
    ("1957 full network", stats["eras"]["full_1957"]["population_curve"]["30"], BRAND_ORANGE),
]

names = [b[0] for b in bars]
vals = [b[1] / 1000 for b in bars]
cols = [b[2] for b in bars]

y_pos = np.arange(len(names))
ax.barh(y_pos, vals, color=cols, height=0.6)
ax.set_yticks(y_pos)
ax.set_yticklabels(names, fontweight='bold')

for i, v in enumerate(vals):
    ax.text(v + 5, i, f"{v:,.0f}k", va="center", fontweight='bold', color=cols[i], fontsize=11)

ax.set_xlabel("Population reachable within 30 minutes from Briggate (thousands)")
ax.xaxis.grid(True)
ax.yaxis.grid(False)
ax.set_axisbelow(True)
ax.spines['left'].set_visible(False)
ax.tick_params(axis='y', length=0)

add_title_subtitle(ax, "The Shrinking Effective Size of Leeds", "How many residents can reach the city centre within 30 minutes by public transport at 08:00")
fig.savefig(PUBLISH_DIR / "effective_size.png", dpi=300, bbox_inches="tight")
print("Saved effective_size.png")
plt.close(fig)

# ── 2. Isochrones Map ───
fig, ax = plt.subplots(figsize=(10, 10))

STYLE = {
    ("full_1957", 30): (BRAND_ORANGE, 1.0),
    ("modern", 30): (BRAND_BLUE, 1.0),
}

# Draw outlines only
for threshold in [30]:
    for f in iso["features"]:
        era = f["properties"]["era"]
        t = f["properties"]["threshold_min"]
        if (era, t) not in STYLE: continue
        
        color, alpha = STYLE[(era, t)]
        for poly in f["geometry"]["coordinates"]:
            for ring_i, ring in enumerate(poly):
                xs = [c[0] for c in ring]
                ys = [c[1] for c in ring]
                # Only outlines, no shading
                ax.plot(xs, ys, color=color, lw=2.5, alpha=alpha, zorder=3)

# Draw tram routes
draw_routes(ax, color="#222", lw=1.0, alpha=0.5)

# Highlight centre (no text annotation)
ax.plot(CENTRE_LON, CENTRE_LAT, "ko", mec="w", ms=10, zorder=6)

from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], color=BRAND_ORANGE, lw=2.5, label='1957 Full Network'),
    Line2D([0], [0], color=BRAND_BLUE, lw=2.5, label='2026 Bus Network'),
    Line2D([0], [0], color='#222', lw=1.5, alpha=0.5, label='1957 Tram Routes'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='k', markersize=10, label='Briggate')
]
ax.legend(handles=legend_elements, loc="upper right", frameon=True, facecolor="white", edgecolor="#CCCCCC", fontsize=11)

ax.set_xlim(-1.70, -1.38)
ax.set_ylim(53.70, 53.88)

# Correct aspect ratio (1 degree lon = cos(lat) degrees lat)
ax.set_aspect(1 / np.cos(np.radians(CENTRE_LAT)))

cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.CartoDB.Positron, attribution=False) # Clean, light basemap
ax.set_xticks([])
ax.set_yticks([])
ax.spines['left'].set_visible(False)
ax.spines['bottom'].set_visible(False)

# More space at the top
ax.set_title("30-Minute Reach from Central Leeds", fontweight="bold", fontsize=16, pad=45)
ax.text(0, 1.02, "Area reachable within 30 mins, 1957 vs 2026. Isochrones show boundary only.", transform=ax.transAxes, ha='left', color='#555555', fontsize=12)

# Scale bar (5 km)
# 1 degree lat is ~111.32 km. 1 degree lon at 53.8 lat is ~65.7 km.
# 5 km in lon = 5 / 65.7 = 0.0761
lon_start = -1.68
lat_bar = 53.71
ax.plot([lon_start, lon_start + 0.0761], [lat_bar, lat_bar], color='black', lw=3, zorder=10)
ax.text(lon_start + (0.0761 / 2), lat_bar + 0.002, "5 km", ha='center', va='bottom', fontsize=11, fontweight='bold', zorder=10, path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground="w")])

# North arrow
ax.annotate("N", xy=(-1.68, 53.87), xytext=(-1.68, 53.855),
            arrowprops=dict(facecolor='black', width=3, headwidth=10, headlength=10),
            ha='center', va='top', fontsize=14, fontweight='bold', zorder=10)

fig.savefig(PUBLISH_DIR / "isochrones_map.png", dpi=300, bbox_inches="tight")
print("Saved isochrones_map.png")
plt.close(fig)


# ── 3. Scatter Plot: Then vs Now ───
fig, ax = plt.subplots(figsize=(8, 8))
tth_full = np.array([float(r["tt_full_1957_min"]) for r in rows])
ttm = np.array([float(r["tt_modern_min"]) for r in rows])
pop = np.array([float(r["population"]) for r in rows])
m = (tth_full <= 60) & (ttm <= 90)

# Calculate difference
diff = ttm[m] - tth_full[m]

# Plot below line (better today)
sc1 = ax.scatter(tth_full[m][diff < 0], ttm[m][diff < 0], 
           s=pop[m][diff < 0] / 30, c=BRAND_BLUE, alpha=0.6, edgecolors="white", linewidths=0.5, zorder=3)
# Plot above line (worse today)
sc2 = ax.scatter(tth_full[m][diff >= 0], ttm[m][diff >= 0], 
           s=pop[m][diff >= 0] / 30, c=BRAND_ORANGE, alpha=0.6, edgecolors="white", linewidths=0.5, zorder=3)

lim = [0, 75]
ax.plot(lim, lim, color="#555555", linestyle="--", lw=1.5, zorder=2)
ax.fill_between(lim, lim, [75, 75], color=BRAND_ORANGE, alpha=0.05, zorder=1)
ax.fill_between(lim, 0, lim, color=BRAND_BLUE, alpha=0.05, zorder=1)

ax.annotate("Journey takes longer in 2026", xy=(15, 60), color=BRAND_ORANGE, fontsize=12, fontweight="bold")
ax.annotate("Journey is faster in 2026", xy=(50, 20), color=BRAND_BLUE, fontsize=12, fontweight="bold")

ax.set_xlim(lim)
ax.set_ylim(lim)
ax.set_xlabel("Minutes to Briggate in 1957", fontweight="bold")
ax.set_ylabel("Minutes to Briggate in 2026", fontweight="bold")

ax.grid(True, linestyle=":", alpha=0.6)

add_title_subtitle(ax, "Every Neighbourhood, Then vs Now", "Travel time to Briggate by public transport for each Leeds LSOA. Dot size = population.")

fig.savefig(PUBLISH_DIR / "scatter_comparison.png", dpi=300, bbox_inches="tight")
print("Saved scatter_comparison.png")
plt.close(fig)

# ── 4. Population Reach Curves ───
fig, ax = plt.subplots(figsize=(9, 6))

x = list(range(5, 65, 5))
walk = [stats["walk_only_curve"].get(str(t), 0) / 1000 for t in x]
trams = [stats["eras"]["tram_1950s"]["population_curve"].get(str(t), 0) / 1000 for t in x]
full_1957 = [stats["eras"]["full_1957"]["population_curve"].get(str(t), 0) / 1000 for t in x]
modern = [stats["eras"]["modern"]["population_curve"].get(str(t), 0) / 1000 for t in x]

ax.plot(x, full_1957, color=BRAND_ORANGE, lw=3, label="1957 Full Network")
ax.plot(x, modern, color=BRAND_BLUE, lw=3, label="2026 Bus Network")
ax.plot(x, trams, color=BRAND_GRAY, lw=2, linestyle="--", label="1957 Trams Only")
ax.plot(x, walk, color="#CCCCCC", lw=2, linestyle=":", label="Walking Only")

ax.set_xlabel("Journey time from Briggate (minutes)", fontweight="bold")
ax.set_ylabel("Population reachable (thousands)", fontweight="bold")
ax.set_xlim(0, 60)
ax.set_ylim(0, max(full_1957[-1], modern[-1]) * 1.05)

ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#CCCCCC", fontsize=11)

add_title_subtitle(ax, "The Reach of Leeds Over Time", "Total population accessible within a given journey time from Briggate, 1957 vs 2026.")

fig.savefig(PUBLISH_DIR / "curves.png", dpi=300, bbox_inches="tight")
print("Saved curves.png")
plt.close(fig)

