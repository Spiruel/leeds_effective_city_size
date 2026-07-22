#!/usr/bin/env python3
import json
import sys
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Setup paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from leeds_trams import ANALYSIS, PROJECT_ROOT

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

BRAND_ORANGE = "#E65100"
BRAND_BLUE = "#0277BD"
BRAND_GRAY = "#9E9E9E"

def add_title_subtitle(ax, title, subtitle, pad=40):
    ax.set_title(title, pad=pad, loc='left')
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, color='#555555', fontsize=12, ha='left')

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

# Load lsoa_times
rows = list(csv.DictReader(open(ANALYSIS / "lsoa_times.csv")))
lsoa_data = {}
for r in rows:
    lsoa_data[r["code"]] = r

# Load car ownership
car_csv = "/tmp/ts045/census2021-ts045-lsoa.csv"
car_data = {}
with open(car_csv) as f:
    reader = csv.DictReader(f)
    for row in reader:
        code = row["geography code"]
        total = int(row["Number of cars or vans: Total: All households"])
        no_car = int(row["Number of cars or vans: No cars or vans in household"])
        if total > 0:
            car_data[code] = no_car / total

# Match data
diffs = []
car_free = []
pops = []
names = []

for code, d in lsoa_data.items():
    if code in car_data:
        tth = float(d["tt_full_1957_min"])
        ttm = float(d["tt_modern_min"])
        # Only look at places that were reasonably accessible in 1957 (e.g. within 60 mins)
        if tth <= 60 and ttm <= 90:
            diffs.append(ttm - tth)
            car_free.append(car_data[code] * 100) # percentage
            pops.append(float(d["population"]))
            names.append(d["name"])

diffs = np.array(diffs)
car_free = np.array(car_free)
pops = np.array(pops)

# Scatter plot: Car ownership vs Transport decay
fig, ax = plt.subplots(figsize=(10, 7))

# Plot regions that are worse off (diff > 0) in orange, better off in blue
worse_mask = diffs > 0
better_mask = diffs <= 0

ax.scatter(car_free[worse_mask], diffs[worse_mask], s=pops[worse_mask] / 40, 
           c=BRAND_ORANGE, alpha=0.6, edgecolors="white", linewidths=0.5, label="Worse today (takes longer)")
ax.scatter(car_free[better_mask], diffs[better_mask], s=pops[better_mask] / 40, 
           c=BRAND_BLUE, alpha=0.6, edgecolors="white", linewidths=0.5, label="Better today (faster)")

# Add a trendline
z = np.polyfit(car_free, diffs, 1)
p = np.poly1d(z)
ax.plot(sorted(car_free), p(sorted(car_free)), "k--", alpha=0.6, lw=1.5, label="Trend")

ax.axhline(0, color="#555555", linestyle="-", lw=1)

ax.set_xlabel("Percentage of households without a car (2021 Census)", fontweight="bold")
ax.set_ylabel("Change in transit time to Briggate (minutes)\nPositive = Slower today vs 1957", fontweight="bold")

# Annotate some key areas. The prompt mentioned "Middleton, Belle Isle, Hunslet, Harehills, Chapeltown"
# We can find the LSOAs that roughly match these names if possible.
# LSOA names are usually "Leeds 001A". But we can just annotate the extreme outliers.
outlier_idx = np.argmax(car_free)
ax.annotate(f"Highest car-free area\n({car_free[outlier_idx]:.1f}%, +{diffs[outlier_idx]:.0f} min)", 
            xy=(car_free[outlier_idx], diffs[outlier_idx]), 
            xytext=(car_free[outlier_idx]-10, diffs[outlier_idx]+5),
            arrowprops=dict(arrowstyle="->", color="#555", lw=1),
            color="#333", fontsize=10, fontweight="bold")

max_delay_idx = np.argmax(diffs)
ax.annotate(f"Most delayed area\n(+{diffs[max_delay_idx]:.0f} min)", 
            xy=(car_free[max_delay_idx], diffs[max_delay_idx]), 
            xytext=(car_free[max_delay_idx]-5, diffs[max_delay_idx]-10),
            arrowprops=dict(arrowstyle="->", color="#555", lw=1),
            color="#333", fontsize=10, fontweight="bold")


ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#CCCCCC", fontsize=10)
ax.grid(True, linestyle=":", alpha=0.6)

add_title_subtitle(ax, "The Transit Penalty for Car-Free Households", "Neighbourhoods with the fewest cars have seen some of the largest increases in transit times since 1957.")

fig.savefig(PUBLISH_DIR / "car_ownership_vs_decay.png", dpi=300, bbox_inches="tight")
print("Saved car_ownership_vs_decay.png")
plt.close(fig)


# Let's make a geographic map colouring LSOAs by car-free percentage, but only plotting the ones that got worse.
import contextily as cx
iso = json.loads((ANALYSIS / "isochrones.geojson").read_text())

# We can plot the LSOAs as dots coloured by car-free % and scaled by how much worse they got.
fig, ax = plt.subplots(figsize=(10, 10))
lats = np.array([float(r["lat"]) for code, r in lsoa_data.items() if code in car_data])
lons = np.array([float(r["lon"]) for code, r in lsoa_data.items() if code in car_data])
c_free = np.array([car_data[code]*100 for code, r in lsoa_data.items() if code in car_data])
t_diff = np.array([float(r["tt_modern_min"]) - float(r["tt_full_1957_min"]) for code, r in lsoa_data.items() if code in car_data])
tth_base = np.array([float(r["tt_full_1957_min"]) for code, r in lsoa_data.items() if code in car_data])

m = (tth_base <= 60) & (t_diff > 5) # only show places that got > 5 mins worse

sc = ax.scatter(lons[m], lats[m], c=c_free[m], cmap="OrRd", s=t_diff[m]*3, edgecolors="k", linewidths=0.3, alpha=0.8, zorder=3)

# Draw tram routes
draw_routes(ax, color="#222", lw=1.0, alpha=0.4)

# Highlight centre
ax.plot(-1.5419, 53.7976, "ko", mec="w", ms=10, zorder=6)
ax.text(-1.5419 + 0.005, 53.7976, "Briggate", fontweight="bold", fontsize=11, zorder=7, 
        path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground="w")])

from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], color='#222', lw=1.5, alpha=0.5, label='1957 Tram Routes'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='k', markersize=10, label='Briggate')
]
ax.legend(handles=legend_elements, loc="upper right", frameon=True, facecolor="white", edgecolor="#CCCCCC", fontsize=11)

ax.set_xlim(-1.70, -1.38)
ax.set_ylim(53.70, 53.88)
cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.CartoDB.Positron, attribution=False) # Clean, light basemap
ax.set_xticks([])
ax.set_yticks([])
ax.spines['left'].set_visible(False)
ax.spines['bottom'].set_visible(False)
ax.set_title("Who Got Left Behind?", fontweight="bold", fontsize=16, pad=45)
ax.text(0.5, 1.02, "Neighbourhoods where transit is >5 mins slower today. Colour = % without a car. Size = delay.", transform=ax.transAxes, ha='center', color='#555555', fontsize=12)

cbar = fig.colorbar(sc, ax=ax, shrink=0.7, label="% Households without a car")

fig.savefig(PUBLISH_DIR / "left_behind_map.png", dpi=300, bbox_inches="tight")
print("Saved left_behind_map.png")
plt.close(fig)

