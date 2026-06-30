import csv
import heapq
import math
import os
from collections import defaultdict

from django.db import connection


GTFS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "GTFS")

WALK_SPEED = 1.4
MAX_WALK_M = 500
TRIP_WEIGHT = 0.02
TRANSFER_TERMINAL_WEIGHT = 0.5
TRANSFER_WALK_BASE = 1.0
ROUTE_SWITCH_PENALTY = 2.0
MAX_WALK_DIRECT_M = 2000


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class Graph:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def load(self):
        if self._loaded:
            return
        print("Carregando grafo de rotas...", flush=True)

        self.adj = defaultdict(list)
        self.stop_coords = {}
        self.stop_names = {}
        self.route_info = {}

        with connection.cursor() as cursor:
            cursor.execute("SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops WHERE stop_lat IS NOT NULL AND stop_lon IS NOT NULL")
            for stop_id, stop_name, lat, lon in cursor.fetchall():
                self.stop_coords[stop_id] = (float(lat), float(lon))
                self.stop_names[stop_id] = stop_name or ""

            cursor.execute("SELECT route_id, route_short_name, route_long_name, route_color, route_text_color FROM routes")
            for rid, short, long_, color, text_color in cursor.fetchall():
                self.route_info[rid] = {
                    "short_name": short or "",
                    "long_name": long_ or "",
                    "color": f"#{color or '999999'}",
                    "text_color": f"#{text_color or 'FFFFFF'}",
                }

            cursor.execute("""
                SELECT t.id, r.route_id, t.direction_id
                FROM trips t
                JOIN routes r ON t.route_id = r.id
            """)
            trip_route_map = {}
            for tid, rid, dir_id in cursor.fetchall():
                trip_route_map[tid] = (rid, dir_id)

            cursor.execute("""
                SELECT t1.trip_id, s1.stop_id AS from_stop, s2.stop_id AS to_stop
                FROM stop_times t1
                JOIN stop_times t2 ON t1.trip_id = t2.trip_id AND t2.stop_sequence = t1.stop_sequence + 1
                JOIN stops s1 ON t1.stop_id = s1.id
                JOIN stops s2 ON t2.stop_id = s2.id
                ORDER BY t1.trip_id, t1.stop_sequence
            """)
            edge_meta = {}
            for trip_fk, from_stop, to_stop in cursor.fetchall():
                key = (from_stop, to_stop)
                rid = trip_route_map.get(trip_fk, ("?", None))[0]
                if key not in edge_meta or edge_meta[key][0] == "walk":
                    edge_meta[key] = ("trip", TRIP_WEIGHT, rid)

        print(f"  Trip edges: {len(edge_meta)}", flush=True)

        transfer_path = os.path.join(GTFS_DIR, "transfers.txt")
        if os.path.exists(transfer_path):
            with open(transfer_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    fr, to = row["from_stop_id"], row["to_stop_id"]
                    if fr == to or fr not in self.stop_coords or to not in self.stop_coords:
                        continue
                    key = (fr, to)
                    if key in edge_meta:
                        continue
                    ttype = row["transfer_type"]
                    mtt_s = row.get("min_transfer_time", "")
                    mtt = int(mtt_s) if mtt_s.strip() else 0
                    if ttype == "0":
                        edge_meta[key] = ("transfer_terminal", TRANSFER_TERMINAL_WEIGHT, None)
                    else:
                        walk_mins = max(mtt, 30) / 60.0
                        w = TRANSFER_WALK_BASE + walk_mins / 10.0
                        edge_meta[key] = ("transfer_walk", w, None)

        transfer_keys = [(fr, to) for (fr, to), (t, _, _) in edge_meta.items()
                         if t in ("transfer_terminal", "transfer_walk")]
        for a, b in transfer_keys:
            if (b, a) in edge_meta and edge_meta[(b, a)][0] in ("transfer_terminal", "transfer_walk"):
                if a > b:
                    del edge_meta[(a, b)]

        for (fr, to), (etyp, w, rid) in edge_meta.items():
            self.adj[fr].append((to, w, etyp, rid))

        print(f"  {len(self.stop_coords)} stops, {len(edge_meta)} edges", flush=True)
        self._loaded = True

    def find_nearest_stops(self, lat, lon, limit=3):
        distances = []
        for sid, (slat, slon) in self.stop_coords.items():
            d = haversine_m(lat, lon, slat, slon)
            if d <= MAX_WALK_M:
                distances.append((d, sid))
        distances.sort()
        return [(sid, d) for d, sid in distances[:limit]]

    def plan_route(self, origin_lat, origin_lon, dest_lat, dest_lon):
        self.load()

        origin_stops = self.find_nearest_stops(origin_lat, origin_lon)
        dest_stops = self.find_nearest_stops(dest_lat, dest_lon)

        if not origin_stops and not dest_stops:
            direct_dist = haversine_m(origin_lat, origin_lon, dest_lat, dest_lon)
            if direct_dist <= MAX_WALK_DIRECT_M:
                return self._build_direct_walk(origin_lat, origin_lon, dest_lat, dest_lon, direct_dist)
            return {"error": f"Nenhum ponto de onibus encontrado. Origem e destino estao a {direct_dist:.0f}m, maximo permitido a pe e {MAX_WALK_DIRECT_M}m."}
        if not origin_stops:
            direct_dist = haversine_m(origin_lat, origin_lon, dest_lat, dest_lon)
            if direct_dist <= MAX_WALK_DIRECT_M:
                return self._build_direct_walk(origin_lat, origin_lon, dest_lat, dest_lon, direct_dist)
            return {"error": "Nenhum ponto de onibus encontrado proximo a origem (500m)"}
        if not dest_stops:
            direct_dist = haversine_m(origin_lat, origin_lon, dest_lat, dest_lon)
            if direct_dist <= MAX_WALK_DIRECT_M:
                return self._build_direct_walk(origin_lat, origin_lon, dest_lat, dest_lon, direct_dist)
            return {"error": "Nenhum ponto de onibus encontrado proximo ao destino (500m)"}

        best_result = None
        best_cost = float("inf")

        for (orig_stop_id, orig_dist), (dest_stop_id, dest_dist) in [
            (o, d) for o in origin_stops for d in dest_stops
        ]:
            result = self._dijkstra(orig_stop_id, dest_stop_id)
            if result:
                walk_cost = (orig_dist / WALK_SPEED) * 0.01 + (dest_dist / WALK_SPEED) * 0.01
                total_cost = result["cost"] + walk_cost
                if total_cost < best_cost:
                    best_cost = total_cost
                    best_result = {
                        **result,
                        "origin_stop_id": orig_stop_id,
                        "dest_stop_id": dest_stop_id,
                        "origin_walk_m": round(orig_dist, 1),
                        "dest_walk_m": round(dest_dist, 1),
                    }

        direct_dist = haversine_m(origin_lat, origin_lon, dest_lat, dest_lon)

        if not best_result:
            if direct_dist <= MAX_WALK_DIRECT_M:
                return self._build_direct_walk(origin_lat, origin_lon, dest_lat, dest_lon, direct_dist)
            return {"error": "Nenhuma rota encontrada entre os pontos informados"}

        bus_segments = 0
        last_route = None
        for n in best_result["path"]:
            if n["edge_type"] == "trip" and n["route_id"] != last_route:
                bus_segments += 1
                last_route = n["route_id"]
        if direct_dist <= 1200 and bus_segments >= 3:
            return self._build_direct_walk(origin_lat, origin_lon, dest_lat, dest_lon, direct_dist)

        return self._build_response(origin_lat, origin_lon, dest_lat, dest_lon, best_result)

    def _dijkstra(self, start_id, end_id):
        if start_id == end_id:
            return {"path": [{"stop_id": start_id, "edge_type": None, "route_id": None}], "cost": 0}

        pq = [(0.0, 0, start_id, None)]
        best = {(start_id, None): 0.0}
        prev = {}
        prev_edge = {}
        seq = 1

        while pq:
            cur_dist, _, cur, cur_route = heapq.heappop(pq)

            state = (cur, cur_route)
            if best.get(state, float("inf")) < cur_dist:
                continue

            if cur == end_id:
                continue

            for neighbor, weight, etyp, rid in self.adj.get(cur, []):
                if etyp == "trip":
                    extra = 0 if (cur_route is None or rid == cur_route) else ROUTE_SWITCH_PENALTY
                    next_route = rid
                elif etyp in ("transfer_terminal", "transfer_walk"):
                    extra = 0
                    next_route = None
                else:
                    extra = 0
                    next_route = None

                nd = cur_dist + weight + extra
                nstate = (neighbor, next_route)

                if nstate not in best or nd < best[nstate]:
                    best[nstate] = nd
                    prev[nstate] = state
                    prev_edge[nstate] = (etyp, rid)
                    heapq.heappush(pq, (nd, seq, neighbor, next_route))
                    seq += 1

        best_final = None
        best_cost = float("inf")
        for (stop, route), cost in best.items():
            if stop == end_id and cost < best_cost:
                best_cost = cost
                best_final = route

        if best_cost == float("inf"):
            return None

        path = []
        state = (end_id, best_final)
        while state[0] != start_id:
            parent_state = prev[state]
            etyp, rid = prev_edge[state]
            path.append({"stop_id": state[0], "edge_type": etyp, "route_id": rid})
            state = parent_state
        path.append({"stop_id": start_id, "edge_type": None, "route_id": None})
        path.reverse()
        return {"path": path, "cost": best_cost}

    def _stop_info(self, stop_id):
        coords = self.stop_coords.get(stop_id)
        name = self.stop_names.get(stop_id, f"Parada {stop_id}")
        return {
            "stop_id": stop_id,
            "stop_name": name,
            "stop_lat": coords[0] if coords else None,
            "stop_lon": coords[1] if coords else None,
        }

    def _build_segments(self, path):
        segments = []
        current_segment = None

        def flush():
            nonlocal current_segment
            if current_segment and len(current_segment["stops"]) >= 2:
                segments.append(current_segment)
            current_segment = None

        for i, node in enumerate(path):
            if i == 0:
                continue
            etyp = node["edge_type"]
            stop = node["stop_id"]
            info = self._stop_info(stop)
            rid = node["route_id"]
            prev_stop = path[i - 1]["stop_id"]
            prev_info = self._stop_info(prev_stop)

            if etyp == "trip":
                if current_segment and current_segment["type"] == "bus" and current_segment["route_id"] == rid:
                    current_segment["stops"].append(stop)
                    current_segment["stop_details"].append(info)
                else:
                    flush()
                    rinfo = self.route_info.get(rid, {"short_name": rid, "long_name": "", "color": "#999999", "text_color": "#FFFFFF"})
                    current_segment = {
                        "type": "bus",
                        "route_id": rid,
                        "short_name": rinfo["short_name"],
                        "long_name": rinfo["long_name"],
                        "color": rinfo["color"],
                        "text_color": rinfo["text_color"],
                        "stops": [prev_stop, stop],
                        "stop_details": [prev_info, info],
                    }

            elif etyp in ("transfer_terminal", "transfer_walk"):
                ttype = "terminal" if etyp == "transfer_terminal" else "walk"
                if (segments and segments[-1]["type"] == "transfer"
                        and segments[-1]["transfer_type"] == ttype
                        and segments[-1]["to_stop"] == prev_stop):
                    segments[-1]["to_stop"] = stop
                    segments[-1]["to_info"] = info
                else:
                    flush()
                    segments.append({
                        "type": "transfer",
                        "transfer_type": ttype,
                        "from_stop": prev_stop,
                        "from_info": prev_info,
                        "to_stop": stop,
                        "to_info": info,
                    })

        flush()
        return segments

    def _build_direct_walk(self, origin_lat, origin_lon, dest_lat, dest_lon, distance):
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[origin_lon, origin_lat], [dest_lon, dest_lat]]},
                    "properties": {"type": "walk", "label": f"Andar {distance:.0f}m ate o destino"},
                }
            ],
        }
        return {
            "origin": {"lat": origin_lat, "lon": origin_lon},
            "destination": {"lat": dest_lat, "lon": dest_lon},
            "geojson": geojson,
            "segments": [],
            "summary": {
                "num_buses": 0,
                "num_transfers": 0,
                "origin_walk_m": round(distance, 1),
                "dest_walk_m": 0,
                "total_stops": 0,
                "origin_stop": {"stop_name": "Origem", "stop_lat": origin_lat, "stop_lon": origin_lon},
                "dest_stop": {"stop_name": "Destino", "stop_lat": dest_lat, "stop_lon": dest_lon},
            },
        }

    def _build_response(self, origin_lat, origin_lon, dest_lat, dest_lon, result):
        path = result["path"]
        segments = self._build_segments(path)
        origin_stop_info = self._stop_info(result["origin_stop_id"])
        dest_stop_info = self._stop_info(result["dest_stop_id"])

        geojson = {"type": "FeatureCollection", "features": []}

        def add_walk_feature(fr_lat, fr_lon, to_lat, to_lon, label):
            if fr_lat is None or to_lat is None:
                return
            geojson["features"].append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[fr_lon, fr_lat], [to_lon, to_lat]]},
                "properties": {"type": "walk", "label": label},
            })

        if result.get("origin_walk_m", 0) > 1:
            add_walk_feature(origin_lat, origin_lon, origin_stop_info["stop_lat"], origin_stop_info["stop_lon"],
                             f"Andar ate {origin_stop_info['stop_name']}")

        for seg in segments:
            if seg["type"] == "bus":
                coords = [[s.get("stop_lon"), s.get("stop_lat")] for s in seg["stop_details"] if s.get("stop_lat")]
                if coords:
                    geojson["features"].append({
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": coords},
                        "properties": {
                            "type": "bus",
                            "route_id": seg["route_id"],
                            "short_name": seg["short_name"],
                            "color": seg["color"],
                        },
                    })
                for sd in seg["stop_details"]:
                    if sd.get("stop_lat"):
                        geojson["features"].append({
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [sd["stop_lon"], sd["stop_lat"]]},
                            "properties": {"type": "stop", "stop_id": sd.get("stop_id", ""),
                                           "stop_name": sd.get("stop_name", "")},
                        })
            elif seg["type"] == "transfer":
                fi, ti = seg["from_info"], seg["to_info"]
                add_walk_feature(fi.get("stop_lat"), fi.get("stop_lon"), ti.get("stop_lat"), ti.get("stop_lon"),
                                 f"Transferir: {fi.get('stop_name', '')} -> {ti.get('stop_name', '')}")
                if fi.get("stop_lat"):
                    geojson["features"].append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [fi["stop_lon"], fi["stop_lat"]]},
                        "properties": {"type": "transfer_point", "stop_id": seg["from_stop"],
                                       "stop_name": fi.get("stop_name", ""),
                                       "transfer_type": seg["transfer_type"]},
                    })

        if result.get("dest_walk_m", 0) > 1:
            add_walk_feature(dest_stop_info["stop_lat"], dest_stop_info["stop_lon"], dest_lat, dest_lon,
                             "Andar ate o destino")

        bus_segments = [s for s in segments if s["type"] == "bus"]
        transfer_segments = [s for s in segments if s["type"] == "transfer"]

        return {
            "origin": {"lat": origin_lat, "lon": origin_lon},
            "destination": {"lat": dest_lat, "lon": dest_lon},
            "geojson": geojson,
            "segments": segments,
            "summary": {
                "num_buses": len(bus_segments),
                "num_transfers": len(transfer_segments),
                "origin_walk_m": result.get("origin_walk_m", 0),
                "dest_walk_m": result.get("dest_walk_m", 0),
                "total_stops": len(path),
                "origin_stop": origin_stop_info,
                "dest_stop": dest_stop_info,
            },
        }
