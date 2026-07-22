#!/usr/bin/env python3
"""Build the COMBINED 1956/57 Leeds network GTFS: 7 tram routes + the full
numbered bus network from the same timetable book -> gtfs_historical_full/."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leeds_trams import DATA, PROJECT_ROOT
from leeds_trams.historical_gtfs import build_feed, bus_line_specs, tram_line_specs

trams = tram_line_specs(DATA / "transcriptions", DATA / "historical" / "route_geometry.json")
buses, skipped = bus_line_specs(
    DATA / "historical" / "bus_lines.json",
    sorted((DATA / "historical").glob("bus_route_geometry_*.json")))
print(f"{len(trams)} tram lines, {len(buses)} bus lines; skipped: {skipped}")

summary = build_feed(trams + buses, PROJECT_ROOT / "gtfs_historical_full")
print(json.dumps({k: v for k, v in summary.items() if k != "routes"}, indent=2))
print(f"{len(summary['routes'])} routes built")
for s in summary["skipped_directions"]:
    print("  skipped:", s)
