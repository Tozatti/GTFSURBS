import json
import os

from sqlalchemy import create_engine

engine = create_engine("sqlite:///./db.sqlite3", connect_args={"check_same_thread": False})

DATA_DIR = "docs/data"
ROUTES_DIR = f"{DATA_DIR}/routes"
STOPS_DIR = f"{DATA_DIR}/stops"

os.makedirs(ROUTES_DIR, exist_ok=True)
os.makedirs(STOPS_DIR, exist_ok=True)

day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

conn = engine.connect()


def select(sql, params=None):
    if params is not None:
        return conn.exec_driver_sql(sql, tuple(params))
    return conn.exec_driver_sql(sql)


def export_routes():
    rows = select(
        "SELECT r.id, r.route_id, r.route_short_name, r.route_long_name,"
        " r.route_type, r.route_color, r.route_text_color,"
        " r.route_sort_order, a.agency_name"
        " FROM routes r LEFT JOIN agencies a ON r.agency_id = a.id"
        " ORDER BY r.route_sort_order, r.route_short_name"
    ).fetchall()

    features = []
    for row in rows:
        color = row.route_color or "999999"
        text_color = row.route_text_color or "FFFFFF"
        features.append({
            "type": "Feature",
            "geometry": None,
            "properties": {
                "id": row.id,
                "route_id": row.route_id,
                "short_name": row.route_short_name or "",
                "long_name": row.route_long_name or "",
                "route_type": row.route_type,
                "color": f"#{color}",
                "text_color": f"#{text_color}",
                "agency_name": row.agency_name or "",
            },
        })

    with open(f"{DATA_DIR}/routes.json", "w", encoding="utf-8") as f:
        json.dump({"features": features}, f, ensure_ascii=False)

    print(f"Exportadas {len(features)} rotas")
    return features


def export_route_details(route_id_str, route_db_id):
    row = select("SELECT route_id, route_short_name, route_long_name, route_type, route_color, route_text_color FROM routes WHERE id = ?", [route_db_id]).fetchone()

    trip = select("SELECT service_id FROM trips WHERE route_id = ? LIMIT 1", [route_db_id]).fetchone()

    days = []
    if trip and trip.service_id:
        cal = select("SELECT * FROM calendars WHERE id = ?", [trip.service_id]).fetchone()
        if cal:
            for day in day_names:
                if getattr(cal, day):
                    days.append(day)

    detail = {
        "route_id": row.route_id,
        "short_name": row.route_short_name or "",
        "long_name": row.route_long_name or "",
        "route_type": row.route_type,
        "color": f"#{row.route_color or '999999'}",
        "text_color": f"#{row.route_text_color or 'FFFFFF'}",
        "agency": "",
        "operating_days": days,
    }

    os.makedirs(f"{ROUTES_DIR}/{route_id_str}", exist_ok=True)
    with open(f"{ROUTES_DIR}/{route_id_str}/detail.json", "w", encoding="utf-8") as f:
        json.dump(detail, f, ensure_ascii=False)


def export_route_shape(route_id_str, route_db_id):
    trips = select("SELECT id, shape_id FROM trips WHERE route_id = ? AND shape_id IS NOT NULL AND shape_id != '' LIMIT 4", [route_db_id]).fetchall()
    if not trips:
        return

    trip_ids = [t.id for t in trips]
    placeholders = ",".join("?" * len(trip_ids))

    shapes_rows = select(
        f"SELECT DISTINCT shape_id FROM trips WHERE id IN ({placeholders}) AND shape_id IS NOT NULL AND shape_id != ''",
        trip_ids,
    ).fetchall()

    shape_ids = [s.shape_id for s in shapes_rows][:4]
    if not shape_ids:
        return

    s_placeholders = ",".join("?" * len(shape_ids))
    shapes = select(
        f"SELECT shape_id, shape_pt_lat, shape_pt_lon, shape_pt_sequence FROM shapes WHERE shape_id IN ({s_placeholders}) ORDER BY shape_id, shape_pt_sequence",
        shape_ids,
    ).fetchall()

    coords_map = {}
    for s in shapes:
        coords_map.setdefault(s.shape_id, []).append([s.shape_pt_lon, s.shape_pt_lat])

    features = [
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": {"shape_id": sid}}
        for sid, coords in coords_map.items()
    ]

    os.makedirs(f"{ROUTES_DIR}/{route_id_str}", exist_ok=True)
    with open(f"{ROUTES_DIR}/{route_id_str}/shape.json", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)


def export_route_stops(route_id_str, route_db_id):
    trips = select("SELECT id FROM trips WHERE route_id = ? LIMIT 5", [route_db_id]).fetchall()
    if not trips:
        return

    trip_ids = [t.id for t in trips]
    placeholders = ",".join("?" * len(trip_ids))

    stop_times = select(
        f"SELECT DISTINCT st.stop_id, s.stop_id as s_id, s.stop_name, s.stop_lat, s.stop_lon, st.stop_sequence"
        f" FROM stop_times st JOIN stops s ON st.stop_id = s.id"
        f" WHERE st.trip_id IN ({placeholders}) ORDER BY st.stop_sequence",
        trip_ids,
    ).fetchall()

    seen = set()
    stops = []
    for st in stop_times:
        if st.stop_id not in seen:
            seen.add(st.stop_id)
            stops.append({
                "stop_id": st.s_id,
                "stop_name": st.stop_name,
                "stop_lat": float(st.stop_lat) if st.stop_lat else None,
                "stop_lon": float(st.stop_lon) if st.stop_lon else None,
                "stop_sequence": st.stop_sequence,
            })

    os.makedirs(f"{ROUTES_DIR}/{route_id_str}", exist_ok=True)
    with open(f"{ROUTES_DIR}/{route_id_str}/stops.json", "w", encoding="utf-8") as f:
        json.dump({"stops": stops}, f, ensure_ascii=False)


def export_stops_index():
    stops = select(
        "SELECT stop_id, stop_name, stop_code, stop_lat, stop_lon FROM stops WHERE stop_lat IS NOT NULL AND stop_lon IS NOT NULL"
    ).fetchall()

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(s.stop_lon), float(s.stop_lat)]},
            "properties": {
                "stop_id": s.stop_id,
                "stop_name": s.stop_name,
                "stop_code": s.stop_code or "",
            },
        }
        for s in stops
    ]

    with open(f"{DATA_DIR}/stops.json", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)

    print(f"Exportadas {len(features)} paradas")
    return [s.stop_id for s in stops]


WEEKDAY_COLS = ["monday", "tuesday", "wednesday", "thursday", "friday"]


def export_stop_times_for_day(stop_id, day_columns):
    if isinstance(day_columns, list):
        condition = " OR ".join(f"{c} = 1" for c in day_columns)
    else:
        condition = f"{day_columns} = 1"

    calendars = select(f"SELECT service_id FROM calendars WHERE {condition}").fetchall()
    service_ids = [c.service_id for c in calendars]
    if not service_ids:
        return []

    s_placeholders = ",".join("?" * len(service_ids))
    times = select(
        f"SELECT t.trip_id, r.route_short_name, r.route_color,"
        f" st.arrival_time, st.departure_time, st.stop_sequence, t.trip_headsign"
        f" FROM stop_times st"
        f" JOIN trips t ON st.trip_id = t.id"
        f" JOIN routes r ON t.route_id = r.id"
        f" WHERE st.stop_id = (SELECT id FROM stops WHERE stop_id = ?)"
        f" AND t.service_ref IN ({s_placeholders})"
        f" ORDER BY st.departure_time LIMIT 50",
        [stop_id] + service_ids,
    ).fetchall()

    return [
        {
            "trip_id": t.trip_id,
            "route_short_name": t.route_short_name or "",
            "route_color": f"#{t.route_color or '999999'}",
            "arrival_time": t.arrival_time or "",
            "departure_time": t.departure_time or "",
            "stop_sequence": t.stop_sequence,
            "headsign": t.trip_headsign or "",
        }
        for t in times
    ]


def export_stop_times(stop_id):
    os.makedirs(f"{STOPS_DIR}/{stop_id}", exist_ok=True)
    data = {
        "weekday": export_stop_times_for_day(stop_id, WEEKDAY_COLS),
        "saturday": export_stop_times_for_day(stop_id, "saturday"),
        "sunday": export_stop_times_for_day(stop_id, "sunday"),
    }
    with open(f"{STOPS_DIR}/{stop_id}/times.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def main():
    print("Exportando dados estáticos do GTFS...\n")

    routes = export_routes()

    print("Exportando detalhes, shapes e paradas das rotas...")
    total = len(routes)
    for i, r in enumerate(routes):
        rid = r["properties"]["route_id"]
        db_id = r["properties"]["id"]
        export_route_details(rid, db_id)
        export_route_shape(rid, db_id)
        export_route_stops(rid, db_id)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{total} rotas...")

    print("Exportando índice de paradas...")
    stop_ids = export_stops_index()

    print("Exportando horários das paradas...")
    for i, sid in enumerate(stop_ids):
        export_stop_times(sid)
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{len(stop_ids)} paradas...")

    conn.close()
    print(f"\nConcluído! Dados exportados para {DATA_DIR}/")


if __name__ == "__main__":
    main()
