#!/usr/bin/env python3
"""Filter the downloaded BODS Yorkshire GTFS to the Leeds area.

Usage: uv run python scripts/filter_modern_gtfs.py [YYYYMMDD]
Default service date: 20260616 (a typical Tuesday in term time).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leeds_trams import DATA
from leeds_trams.modern_gtfs import filter_feed

date = sys.argv[1] if len(sys.argv) > 1 else "20260616"
zip_path = DATA / "modern" / "itm_yorkshire_gtfs.zip"
out_dir = DATA / "modern" / "filtered"

stats = filter_feed(zip_path, out_dir, date)
print(json.dumps(stats, indent=2))
(out_dir / "filter_stats.json").write_text(json.dumps(stats, indent=2))
