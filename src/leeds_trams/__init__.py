"""Leeds 1950s tram GTFS reconstruction and past-vs-present accessibility analysis."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA = PROJECT_ROOT / "data"
ANALYSIS = PROJECT_ROOT / "analysis"

# Leeds city centre reference point: Briggate (tram-era hub, still the retail core)
CENTRE_LAT = 53.7976
CENTRE_LON = -1.5419

# Walking model (applied identically to both eras).
# Env overrides (LT_WALK_KMH, LT_DETOUR) exist for sensitivity analysis only.
import os as _os

WALK_SPEED_M_MIN = float(_os.environ.get("LT_WALK_KMH", "4.8")) * 1000 / 60
WALK_DETOUR_FACTOR = float(_os.environ.get("LT_DETOUR", "1.3"))  # crow-fly -> street
EFFECTIVE_WALK_M_MIN = WALK_SPEED_M_MIN / WALK_DETOUR_FACTOR  # m/min over crow-fly distance

MAX_ACCESS_WALK_MIN = 20.0       # max walk to first stop / from last stop
MAX_TRANSFER_WALK_M = 400.0      # crow-fly metres between stops for a transfer
TRANSFER_PENALTY_MIN = 1.0       # perceived cost of changing vehicle
