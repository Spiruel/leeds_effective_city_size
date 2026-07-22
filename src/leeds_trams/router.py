"""Earliest-arrival public transport routing (RAPTOR) over a GTFS directory.

Used identically for the 1950s tram feed and the filtered modern feed, so the
two eras are compared with the same algorithm and walking model.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import (EFFECTIVE_WALK_M_MIN, MAX_ACCESS_WALK_MIN, MAX_TRANSFER_WALK_M,
               TRANSFER_PENALTY_MIN)
from .geometry import GridIndex

INF = float("inf")


def _gtfs_time_to_min(t: str) -> float:
    h, m, s = t.split(":")
    return int(h) * 60 + int(m) + int(s) / 60


class Feed:
    def __init__(self, gtfs_dir: Path, service_id: str | None = None):
        """Load a GTFS directory. If service_id is given, keep only trips on it
        (historical feed); otherwise keep every trip (pre-filtered modern feed)."""
        self.dir = gtfs_dir

        self.stop_ids: list[str] = []
        self.stop_names: list[str] = []
        lats, lons = [], []
        idx_of: dict[str, int] = {}
        with open(gtfs_dir / "stops.txt") as f:
            for row in csv.DictReader(f):
                idx_of[row["stop_id"]] = len(self.stop_ids)
                self.stop_ids.append(row["stop_id"])
                self.stop_names.append(row.get("stop_name", ""))
                lats.append(float(row["stop_lat"]))
                lons.append(float(row["stop_lon"]))
        self.lat = np.array(lats)
        self.lon = np.array(lons)
        self.n_stops = len(self.stop_ids)

        keep_trip: dict[str, str] = {}
        with open(gtfs_dir / "trips.txt") as f:
            for row in csv.DictReader(f):
                if service_id is None or row.get("service_id") == service_id:
                    keep_trip[row["trip_id"]] = row["route_id"]

        # Collect stop sequences per trip
        trip_stops: dict[str, list[tuple[int, float, float, int]]] = defaultdict(list)
        with open(gtfs_dir / "stop_times.txt") as f:
            for row in csv.DictReader(f):
                tid = row["trip_id"]
                if tid not in keep_trip:
                    continue
                trip_stops[tid].append((int(row["stop_sequence"]),
                                        _gtfs_time_to_min(row["arrival_time"]),
                                        _gtfs_time_to_min(row["departure_time"]),
                                        idx_of[row["stop_id"]]))

        # Group trips into patterns (identical stop sequence on the same route)
        pattern_key_to_id: dict[tuple, int] = {}
        self.pattern_stops: list[list[int]] = []        # pattern -> stop idx sequence
        pattern_trips: list[list[tuple[float, list[float], list[float]]]] = []
        for tid, rows in trip_stops.items():
            rows.sort()
            seq = [r[3] for r in rows]
            arr = [r[1] for r in rows]
            dep = [r[2] for r in rows]
            key = (keep_trip[tid], tuple(seq))
            pid = pattern_key_to_id.get(key)
            if pid is None:
                pid = len(self.pattern_stops)
                pattern_key_to_id[key] = pid
                self.pattern_stops.append(seq)
                pattern_trips.append([])
            pattern_trips[pid].append((dep[0], arr, dep))

        # Per pattern: arrays sorted by first departure
        self.pattern_arr: list[np.ndarray] = []   # (n_trips, n_seq)
        self.pattern_dep: list[np.ndarray] = []
        for pid, trips in enumerate(pattern_trips):
            trips.sort(key=lambda t: t[0])
            self.pattern_arr.append(np.array([t[1] for t in trips]))
            self.pattern_dep.append(np.array([t[2] for t in trips]))

        # stop -> [(pattern, position)]
        self.stop_patterns: list[list[tuple[int, int]]] = [[] for _ in range(self.n_stops)]
        for pid, seq in enumerate(self.pattern_stops):
            for pos, s in enumerate(seq):
                self.stop_patterns[s].append((pid, pos))

        # Footpath transfers between nearby stops
        grid = GridIndex(MAX_TRANSFER_WALK_M)
        for i in range(self.n_stops):
            grid.add(self.lat[i], self.lon[i])
        self.transfers: list[list[tuple[int, float]]] = [[] for _ in range(self.n_stops)]
        for i in range(self.n_stops):
            for j, d in grid.near(self.lat[i], self.lon[i], MAX_TRANSFER_WALK_M):
                if j != i:
                    self.transfers[i].append((j, d / EFFECTIVE_WALK_M_MIN))

        self._grid = grid
        self.n_trips = sum(len(t) for t in pattern_trips)

    def stops_near(self, lat: float, lon: float, radius_m: float):
        return self._grid.near(lat, lon, radius_m)


def raptor(feed: Feed, origin_lat: float, origin_lon: float, dep_min: float,
           max_rounds: int = 4) -> np.ndarray:
    """Earliest arrival time (minutes) at every stop, departing the origin
    point at dep_min. Walk access/egress and transfers per the walking model."""
    arrival = np.full(feed.n_stops, INF)
    best = np.full(feed.n_stops, INF)

    marked: set[int] = set()
    access_radius = MAX_ACCESS_WALK_MIN * EFFECTIVE_WALK_M_MIN
    for s, d in feed.stops_near(origin_lat, origin_lon, access_radius):
        t = dep_min + d / EFFECTIVE_WALK_M_MIN
        if t < arrival[s]:
            arrival[s] = best[s] = t
            marked.add(s)

    for rnd in range(max_rounds):
        # Ride phase
        queue: dict[int, int] = {}  # pattern -> earliest boarding position
        for s in marked:
            for pid, pos in feed.stop_patterns[s]:
                if pid not in queue or pos < queue[pid]:
                    queue[pid] = pos
        new_marked: set[int] = set()
        board_cost = TRANSFER_PENALTY_MIN if rnd > 0 else 0.0
        for pid, start_pos in queue.items():
            seq = feed.pattern_stops[pid]
            dep = feed.pattern_dep[pid]
            arr = feed.pattern_arr[pid]
            trip = -1
            for pos in range(start_pos, len(seq)):
                s = seq[pos]
                if trip >= 0 and arr[trip, pos] < best[s]:
                    arrival[s] = best[s] = arr[trip, pos]
                    new_marked.add(s)
                # Could we catch an earlier trip here?
                if best[s] < INF:
                    ready = best[s] + board_cost
                    t = int(np.searchsorted(dep[:, pos], ready))
                    if t < len(dep) and (trip < 0 or t < trip) and dep[t, pos] >= ready:
                        trip = t
            # note: trips assumed FIFO within a pattern (no overtaking)
        if not new_marked:
            break
        # Footpath phase
        foot_marked = set(new_marked)
        for s in new_marked:
            for j, wt in feed.transfers[s]:
                t = arrival[s] + wt
                if t < best[j]:
                    arrival[j] = best[j] = t
                    foot_marked.add(j)
        marked = foot_marked

    return best
