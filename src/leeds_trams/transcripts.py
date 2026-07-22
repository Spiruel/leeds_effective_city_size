"""Load and normalise the vision-transcribed timetable JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from . import DATA

DAY_TYPES = ("monday_to_friday", "saturday", "sunday")

# Canonical names for timing points that appear under printed variants
CANONICAL = {
    "templenewsam": "Temple Newsam",
    "temple newsam": "Temple Newsam",
    "swingate": "Swinegate",
    "swinegate": "Swinegate",
    "swingegate": "Swinegate",
    "dewsbury road terminus": "Dewsbury Road",
    "infirmary st": "Infirmary Street",
    "south accom rd": "South Accommodation Road",
    "central bus station": "Central Bus Station",
    "bus station": "Central Bus Station",
}


def canonical_stop(name: str) -> str:
    n = " ".join(name.replace(".", "").split())
    return CANONICAL.get(n.lower(), n)


def hhmm_to_min(t: str) -> float:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def expand_pattern(pattern: list[dict]) -> list[float]:
    """Expand a service_pattern (departures + frequency blocks) into a sorted
    list of departure minutes-after-midnight for the first stop."""
    deps: set[float] = set()
    for item in pattern:
        if item["type"] == "departure":
            deps.add(hhmm_to_min(item["time"]))
        elif item["type"] == "frequency":
            start, end = hhmm_to_min(item["start"]), hhmm_to_min(item["end"])
            if end < start:  # crosses midnight
                end += 24 * 60
            h = float(item["headway_min"])
            t = start
            while t <= end + 1e-6:
                deps.add(round(t, 1))
                t += h
        else:
            raise ValueError(f"unknown service_pattern type: {item['type']}")
    return sorted(deps)


def load_transcriptions(path: Path | None = None) -> list[dict]:
    """Load all page transcriptions, with canonicalised stop names."""
    tdir = path or (DATA / "transcriptions")
    pages = []
    for f in sorted(tdir.glob("p*.json")):
        page = json.loads(f.read_text())
        for table in page["day_tables"]:
            for direction in table["directions"]:
                for stop in direction["stops"]:
                    stop["name"] = canonical_stop(stop["name"])
        pages.append(page)
    return pages


def validate(pages: list[dict]) -> list[str]:
    """Internal-consistency checks; returns a list of human-readable issues."""
    issues = []
    for page in pages:
        key = page["page_key"]
        for table in page["day_tables"]:
            if table["day_type"] not in DAY_TYPES:
                issues.append(f"{key}: unknown day_type {table['day_type']}")
            for d in table["directions"]:
                name = f"{key}/{table['day_type']}/{d['direction_name']}"
                offs = d["stop_offsets_min"]
                if len(offs) != len(d["stops"]):
                    issues.append(f"{name}: {len(d['stops'])} stops vs {len(offs)} offsets")
                if offs != sorted(offs) or offs[0] != 0:
                    issues.append(f"{name}: offsets not increasing from 0: {offs}")
                deps = expand_pattern(d["service_pattern"])
                if not deps:
                    issues.append(f"{name}: no departures")
                    continue
                first, last = hhmm_to_min(d["first_departure"]), hhmm_to_min(d["last_departure"])
                if abs(deps[0] - first) > 0.5:
                    issues.append(f"{name}: first dep {deps[0]} != declared {first}")
                if abs(deps[-1] - last) > 0.5 and abs(deps[-1] - 24 * 60 - last) > 0.5:
                    issues.append(f"{name}: last dep {deps[-1]} != declared {last}")
                gaps = [b - a for a, b in zip(deps, deps[1:])]
                big = [g for g in gaps if g > 65]
                if big:
                    issues.append(f"{name}: service gaps >65 min: {big}")
    return issues
