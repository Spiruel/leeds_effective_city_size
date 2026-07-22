#!/usr/bin/env python3
"""Build the full 1950s Leeds tram GTFS feed from the page transcriptions
and the researched route geometry."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leeds_trams import DATA, PROJECT_ROOT
from leeds_trams.historical_gtfs import build
from leeds_trams.transcripts import load_transcriptions, validate

issues = validate(load_transcriptions())
if issues:
    print("Transcription validation issues:")
    for i in issues:
        print(" -", i)
    sys.exit(1)
print("Transcriptions validate clean.")

# Era: late 1956 - summer 1957 (see data/historical/era_notes.md)
summary = build(
    transcriptions_dir=DATA / "transcriptions",
    geometry_path=DATA / "historical" / "route_geometry.json",
    out_dir=PROJECT_ROOT / "gtfs_historical",
    era_start="19561001", era_end="19570927",
)
print(json.dumps(summary, indent=2))
