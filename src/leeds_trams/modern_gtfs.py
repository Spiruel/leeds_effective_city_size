"""Filter the BODS Yorkshire GTFS down to the Leeds area for one service date.

The national/regional feeds are huge (stop_times.txt ~420 MB); we stream them
and keep only trips that (a) run on the chosen service date and (b) call at
at least one stop within `radius_km` of Leeds city centre.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from pathlib import Path

from . import CENTRE_LAT, CENTRE_LON
from .geometry import haversine_m

WEEKDAY_COLS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _open_csv(zf: zipfile.ZipFile, name: str):
    return csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="utf-8-sig"))


def active_service_ids(zf: zipfile.ZipFile, yyyymmdd: str) -> set[str]:
    date = datetime.strptime(yyyymmdd, "%Y%m%d")
    dow = WEEKDAY_COLS[date.weekday()]
    active: set[str] = set()
    for row in _open_csv(zf, "calendar.txt"):
        if row["start_date"] <= yyyymmdd <= row["end_date"] and row[dow] == "1":
            active.add(row["service_id"])
    if "calendar_dates.txt" in zf.namelist():
        for row in _open_csv(zf, "calendar_dates.txt"):
            if row["date"] == yyyymmdd:
                if row["exception_type"] == "1":
                    active.add(row["service_id"])
                elif row["exception_type"] == "2":
                    active.discard(row["service_id"])
    return active


def filter_feed(zip_path: Path, out_dir: Path, yyyymmdd: str, radius_km: float = 30.0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    stats: dict = {"service_date": yyyymmdd, "radius_km": radius_km}

    with zipfile.ZipFile(zip_path) as zf:
        # 1. Stops within radius
        stops_rows = {}
        for row in _open_csv(zf, "stops.txt"):
            try:
                lat, lon = float(row["stop_lat"]), float(row["stop_lon"])
            except ValueError:
                continue
            if haversine_m(CENTRE_LAT, CENTRE_LON, lat, lon) <= radius_km * 1000:
                stops_rows[row["stop_id"]] = (row["stop_name"], lat, lon)
        stats["stops_in_radius"] = len(stops_rows)

        # 2. Services active on the chosen date
        active = active_service_ids(zf, yyyymmdd)
        stats["active_services"] = len(active)

        # 3. Trips on active services
        trip_route: dict[str, str] = {}
        for row in _open_csv(zf, "trips.txt"):
            if row["service_id"] in active:
                trip_route[row["trip_id"]] = row["route_id"]
        stats["active_trips"] = len(trip_route)

        # 4. Stream stop_times: keep active trips that touch the radius.
        #    BODS feeds are grouped by trip_id; we buffer one trip at a time.
        kept_trips: set[str] = set()
        n_rows = 0
        with open(out_dir / "stop_times.txt", "w", newline="") as out_f:
            w = csv.writer(out_f)
            w.writerow(["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"])

            cur_trip, buf, touches = None, [], False
            seen_done: set[str] = set()

            def flush():
                nonlocal n_rows
                if cur_trip is not None and touches and buf:
                    kept_trips.add(cur_trip)
                    w.writerows(buf)
                    n_rows += len(buf)

            for row in _open_csv(zf, "stop_times.txt"):
                tid = row["trip_id"]
                if tid not in trip_route:
                    continue
                if tid != cur_trip:
                    flush()
                    if tid in seen_done:
                        raise RuntimeError("stop_times.txt not grouped by trip_id")
                    if cur_trip is not None:
                        seen_done.add(cur_trip)
                    cur_trip, buf, touches = tid, [], False
                if row["stop_id"] in stops_rows:
                    touches = True
                buf.append([tid, row["arrival_time"], row["departure_time"],
                            row["stop_id"], row["stop_sequence"]])
            flush()
        stats["kept_trips"] = len(kept_trips)
        stats["kept_stop_time_rows"] = n_rows

        # 5. Write trips / routes / stops for what we kept
        kept_routes = {trip_route[t] for t in kept_trips}
        with open(out_dir / "trips.txt", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["trip_id", "route_id"])
            for t in kept_trips:
                w.writerow([t, trip_route[t]])

        with open(out_dir / "routes.txt", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["route_id", "route_short_name", "route_type", "agency_id"])
            n = 0
            for row in _open_csv(zf, "routes.txt"):
                if row["route_id"] in kept_routes:
                    w.writerow([row["route_id"], row.get("route_short_name", ""),
                                row.get("route_type", ""), row.get("agency_id", "")])
                    n += 1
            stats["kept_routes"] = n

        # Stops referenced by kept trips may lie outside the radius; keep those too.
        referenced: set[str] = set()
        with open(out_dir / "stop_times.txt") as f:
            for row in csv.DictReader(f):
                referenced.add(row["stop_id"])
        with open(out_dir / "stops.txt", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["stop_id", "stop_name", "stop_lat", "stop_lon"])
            n = 0
            for row in _open_csv(zf, "stops.txt"):
                if row["stop_id"] in referenced:
                    w.writerow([row["stop_id"], row["stop_name"], row["stop_lat"], row["stop_lon"]])
                    n += 1
            stats["kept_stops"] = n

    return stats
