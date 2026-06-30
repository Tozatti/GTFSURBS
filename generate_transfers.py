#!/usr/bin/env python3
"""Gera transfers.txt para o GTFS de Curitiba.

Estrategias:
  1. Transferencias recomendadas (type=0) entre paradas de um mesmo terminal
  2. Transferencias com tempo minimo (type=1) entre paradas proximas (100m)
  3. Co-localizadas (type=0) entre paradas muito proximas (30m)
"""

import csv
import math
import os
from collections import defaultdict

GTFS_DIR = os.path.join(os.path.dirname(__file__), "GTFS")
OUTPUT = os.path.join(GTFS_DIR, "transfers.txt")

WALKING_SPEED = 1.4  # m/s
NEARBY_DISTANCE = 100  # m
COLOCATED_DISTANCE = 30  # m

# WGS84 constants for Curitiba (approx -25.45 degrees latitude)
LAT_M = 111_320.0
LON_M = 111_320.0 * math.cos(math.radians(-25.45))


def lat_lon_to_meters(lat, lon):
    """Convert lat/lon to approximate meters from origin."""
    return lat * LAT_M, lon * LON_M


def haversine_m(lat1, lon1, lat2, lon2):
    """Haversine distance in meters between two lat/lon points."""
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_grid_index(stops, cell_size=100):
    """Build spatial grid index: grid_cell_key -> list of stop dicts."""
    grid = defaultdict(list)
    for s in stops:
        y, x = lat_lon_to_meters(float(s["stop_lat"]), float(s["stop_lon"]))
        cx = int(x // cell_size)
        cy = int(y // cell_size)
        grid[(cx, cy)].append(s)
    return grid


def get_nearby_cells(cx, cy):
    """Return all cell keys within Chebyshev distance of 1."""
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            yield (cx + dx, cy + dy)


def load_stops():
    path = os.path.join(GTFS_DIR, "stops.txt")
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    print("Carregando stops...")
    stops = load_stops()
    stop_map = {s["stop_id"]: s for s in stops}
    print(f"  {len(stops)} stops carregados")

    # Build terminal lookup: terminal_id -> list of child stops
    terminals = defaultdict(list)
    for s in stops:
        if s["parent_station"]:
            terminals[s["parent_station"]].append(s)

    for s in stops:
        if s["location_type"] == "1":
            if s["stop_id"] not in terminals:
                terminals[s["stop_id"]] = []
            if s not in terminals[s["stop_id"]]:
                terminals[s["stop_id"]].insert(0, s)

    print(f"  {len(terminals)} terminais com paradas filhas")

    seen_dirs = set()
    seen_pairs = set()
    result = []

    def add_transfer(fr, to, typ, time_val=""):
        key = (fr, to)
        if key not in seen_dirs:
            seen_dirs.add(key)
            result.append({
                "from_stop_id": fr,
                "to_stop_id": to,
                "transfer_type": typ,
                "min_transfer_time": str(time_val) if time_val else "",
            })

    def add_bidirectional(a, b, typ, time_val=""):
        if not isinstance(time_val, str):
            time_val = str(time_val)
        add_transfer(a, b, typ, time_val)
        add_transfer(b, a, typ, time_val)

    # --- Strategy 1: Terminal internal transfers (type=0) ---
    print("\nEstrategia 1: Transferencias dentro de terminais...")
    count_t1 = 0
    for term_id, children in terminals.items():
        ids = [c["stop_id"] for c in children]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                add_bidirectional(ids[i], ids[j], "0")
                count_t1 += 1
    print(f"  {count_t1} pares bidirecionais gerados")

    # --- Strategy 2 & 3: Nearby stops & co-located stops ---
    print("\nEstrategias 2 e 3: Paradas proximas e co-localizadas...")
    grid = build_grid_index(stops)
    count_t2 = 0
    count_t3 = 0

    for (cx, cy), cell_stops in grid.items():
        nearby_ids = set()
        for ncx, ncy in get_nearby_cells(cx, cy):
            for ns in grid.get((ncx, ncy), []):
                nearby_ids.add(ns["stop_id"])

        for s in cell_stops:
            sid = s["stop_id"]
            slat = float(s["stop_lat"])
            slon = float(s["stop_lon"])
            for other_id in nearby_ids:
                if other_id <= sid:
                    continue
                o = stop_map[other_id]
                dist = haversine_m(slat, slon, float(o["stop_lat"]), float(o["stop_lon"]))
                if dist > NEARBY_DISTANCE:
                    continue

                canon = (sid, other_id) if sid < other_id else (other_id, sid)
                if canon in seen_pairs:
                    continue
                seen_pairs.add(canon)

                if dist <= COLOCATED_DISTANCE:
                    add_bidirectional(sid, other_id, "0")
                    count_t3 += 1
                else:
                    walk_time = int(dist / WALKING_SPEED)
                    if walk_time < 30:
                        walk_time = 30
                    add_bidirectional(sid, other_id, "1", walk_time)
                    count_t2 += 1

    print(f"  {count_t3} co-localizadas (type=0, ate {COLOCATED_DISTANCE}m)")
    print(f"  {count_t2} proximas com tempo (type=1, ate {NEARBY_DISTANCE}m)")

    # --- Write transfers.txt ---
    total = len(result)
    print(f"\nTotal: {total} registros de transferencia")

    fieldnames = ["from_stop_id", "to_stop_id", "transfer_type", "min_transfer_time"]
    with open(OUTPUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for t in result:
            writer.writerow(t)

    print(f"Escrito em: {OUTPUT}")
    return 0


if __name__ == "__main__":
    exit(main())
