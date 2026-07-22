#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from leeds_trams import ANALYSIS, PROJECT_ROOT

PUBLISH_DIR = ANALYSIS / "publish"
PUBLISH_DIR.mkdir(exist_ok=True)

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

ext_stats = json.loads((ANALYSIS / "extended_stats.json").read_text())

# 1. Jobs Accessibility (Bar Chart)
fig, ax = plt.subplots(figsize=(10, 6))

times = ["15", "30", "45", "60"]
jobs_1957 = [ext_stats["jobs_weighted"]["curves"]["full_1957"][t]/1000 for t in times]
jobs_2026 = [ext_stats["jobs_weighted"]["curves"]["modern"][t]/1000 for t in times]

x = np.arange(len(times))
width = 0.35

ax.bar(x - width/2, jobs_1957, width, label='1957 Full Network', color=BRAND_ORANGE)
ax.bar(x + width/2, jobs_2026, width, label='2026 Bus Network', color=BRAND_BLUE)

ax.set_xticks(x)
ax.set_xticklabels([f"{t} mins" for t in times], fontweight='bold')
ax.set_ylabel("Jobs reachable (thousands)", fontweight="bold")
ax.legend(loc='upper left', frameon=True, facecolor="white", edgecolor="#CCCCCC", fontsize=11)
ax.yaxis.grid(True)
ax.xaxis.grid(False)

for i, v in enumerate(jobs_1957):
    ax.text(i - width/2, v + 5, f"{v:.0f}k", ha="center", va="bottom", fontweight="bold", color=BRAND_ORANGE)
for i, v in enumerate(jobs_2026):
    ax.text(i + width/2, v + 5, f"{v:.0f}k", ha="center", va="bottom", fontweight="bold", color=BRAND_BLUE)

add_title_subtitle(ax, "Access to Employment, Then vs Now", "Number of jobs reachable from Briggate within given time thresholds.")

fig.savefig(PUBLISH_DIR / "jobs_accessibility.png", dpi=300, bbox_inches="tight")
print("Saved jobs_accessibility.png")
plt.close(fig)

# 2. Rail Integration (Line Chart)
fig, ax = plt.subplots(figsize=(9, 6))

x_vals = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
curve_1957 = [ext_stats["rail"]["full_1957_with_rail_curve"][str(t)]/1000 for t in x_vals]
curve_2026 = [ext_stats["rail"]["modern_with_rail_curve"][str(t)]/1000 for t in x_vals]

stats = json.loads((ANALYSIS / "stats.json").read_text())
curve_1957_norail = [stats["eras"]["full_1957"]["population_curve"].get(str(t), 0)/1000 for t in x_vals]
curve_2026_norail = [stats["eras"]["modern"]["population_curve"].get(str(t), 0)/1000 for t in x_vals]

ax.plot(x_vals, curve_1957, color=BRAND_ORANGE, lw=3, label="1957 Tram/Bus + Rail")
ax.plot(x_vals, curve_1957_norail, color=BRAND_ORANGE, lw=2, linestyle="--", label="1957 Tram/Bus Only", alpha=0.6)

ax.plot(x_vals, curve_2026, color=BRAND_BLUE, lw=3, label="2026 Bus + Rail")
ax.plot(x_vals, curve_2026_norail, color=BRAND_BLUE, lw=2, linestyle="--", label="2026 Bus Only", alpha=0.6)

ax.set_xlabel("Journey time from Briggate (minutes)", fontweight="bold")
ax.set_ylabel("Population reachable (thousands)", fontweight="bold")
ax.set_xlim(0, 60)
ax.set_ylim(0, max(curve_2026)*1.05)
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#CCCCCC", fontsize=11)

add_title_subtitle(ax, "The Impact of the Heavy Rail Network", "Population accessible when incorporating local heavy rail services.")

fig.savefig(PUBLISH_DIR / "rail_integration.png", dpi=300, bbox_inches="tight")
print("Saved rail_integration.png")
plt.close(fig)

# 3. St James Hospital (Bar chart - 30/45 min)
fig, ax = plt.subplots(figsize=(10, 6))

stj_1957_30 = ext_stats["origins"]["st_james_hospital"]["full_1957"]["pop30"] / 1000
stj_2026_30 = ext_stats["origins"]["st_james_hospital"]["modern"]["pop30"] / 1000
stj_1957_45 = ext_stats["origins"]["st_james_hospital"]["full_1957"]["pop45"] / 1000
stj_2026_45 = ext_stats["origins"]["st_james_hospital"]["modern"]["pop45"] / 1000

labels = ["30 Minutes", "45 Minutes"]
vals_1957 = [stj_1957_30, stj_1957_45]
vals_2026 = [stj_2026_30, stj_2026_45]

x = np.arange(len(labels))
ax.bar(x - width/2, vals_1957, width, label='1957 Full Network', color=BRAND_ORANGE)
ax.bar(x + width/2, vals_2026, width, label='2026 Bus Network', color=BRAND_BLUE)

ax.set_xticks(x)
ax.set_xticklabels(labels, fontweight='bold')
ax.set_ylabel("Population reachable (thousands)", fontweight="bold")
ax.legend(loc='upper left', frameon=True, facecolor="white", edgecolor="#CCCCCC", fontsize=11)
ax.yaxis.grid(True)
ax.xaxis.grid(False)

for i, v in enumerate(vals_1957):
    ax.text(i - width/2, v + 5, f"{v:.0f}k", ha="center", va="bottom", fontweight="bold", color=BRAND_ORANGE)
for i, v in enumerate(vals_2026):
    ax.text(i + width/2, v + 5, f"{v:.0f}k", ha="center", va="bottom", fontweight="bold", color=BRAND_BLUE)

add_title_subtitle(ax, "Access to St James's Hospital", "Total population that can reach St James's Hospital within 30 and 45 minutes.")

fig.savefig(PUBLISH_DIR / "st_james_hospital_reach.png", dpi=300, bbox_inches="tight")
print("Saved st_james_hospital_reach.png")
plt.close(fig)

# 4. Car vs Transit (Bar chart - 30 mins)
fig, ax = plt.subplots(figsize=(10, 6))

car_peak_30 = ext_stats["car"]["curve"]["30"] / 1000
car_free_30 = ext_stats["car"]["freeflow_curve"]["30"] / 1000
t1957_30 = stats["eras"]["full_1957"]["population_curve"]["30"] / 1000
t2026_30 = stats["eras"]["modern"]["population_curve"]["30"] / 1000

labels = ["Car (Freeflow)", "Car (Rush Hour)", "1957 Transit", "2026 Transit"]
vals = [car_free_30, car_peak_30, t1957_30, t2026_30]
colors = ["#757575", "#BDBDBD", BRAND_ORANGE, BRAND_BLUE]

x_pos = np.arange(len(labels))
ax.bar(x_pos, vals, color=colors, width=0.6)

ax.set_xticks(x_pos)
ax.set_xticklabels(labels, fontweight='bold')
ax.set_ylabel("Population reachable (thousands)", fontweight="bold")
ax.yaxis.grid(True)
ax.xaxis.grid(False)

for i, v in enumerate(vals):
    ax.text(i, v + 10, f"{v:,.0f}k", ha="center", va="bottom", fontweight="bold", color=colors[i])

add_title_subtitle(ax, "The Unbeatable Car?", "Population reachable within 30 minutes from Briggate, comparing driving vs public transit.")

fig.savefig(PUBLISH_DIR / "car_vs_transit.png", dpi=300, bbox_inches="tight")
print("Saved car_vs_transit.png")
plt.close(fig)

# 5. Traffic Stress Test (Bar chart - 30 mins)
fig, ax = plt.subplots(figsize=(10, 6))

hc_10 = ext_stats["haircut"]["minus10pct"]["pop30"] / 1000
hc_20 = ext_stats["haircut"]["minus20pct"]["pop30"] / 1000

labels_stress = ["1957 (Scheduled)", "1957 (10% Slower)", "1957 (20% Slower)", "2026 Transit"]
vals_stress = [t1957_30, hc_10, hc_20, t2026_30]
colors_stress = [BRAND_ORANGE, "#F57C00", "#FF9800", BRAND_BLUE]

x_pos_str = np.arange(len(labels_stress))
ax.bar(x_pos_str, vals_stress, color=colors_stress, width=0.6)

ax.set_xticks(x_pos_str)
ax.set_xticklabels(labels_stress, fontweight='bold')
ax.set_ylabel("Population reachable (thousands)", fontweight="bold")
ax.yaxis.grid(True)
ax.xaxis.grid(False)

for i, v in enumerate(vals_stress):
    ax.text(i, v + 5, f"{v:.0f}k", ha="center", va="bottom", fontweight="bold", color=colors_stress[i])

add_title_subtitle(ax, "Traffic Jam Stress Test", "30-minute reach if historical 1957 transit speeds are artificially slowed by simulated traffic.")

fig.savefig(PUBLISH_DIR / "traffic_stress_test.png", dpi=300, bbox_inches="tight")
print("Saved traffic_stress_test.png")
plt.close(fig)
