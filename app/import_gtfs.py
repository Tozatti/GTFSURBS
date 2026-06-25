import csv
import io
import os
import zipfile
from datetime import date, datetime

import requests
from sqlalchemy.orm import Session

from .database import SessionLocal, engine, Base
from .models import Agency, Route, Stop, Trip, StopTime, Shape, Calendar, CalendarDate

GTFS_URL = "http://files.urbs.curitiba.pr.gov.br/google/google_transit.zip"


def download_zip() -> bytes:
    os.makedirs("feeds", exist_ok=True)
    cached = os.path.join("feeds", "google_transit.zip")

    if os.path.exists(cached):
        print("Usando zip em cache...")
        with open(cached, "rb") as f:
            return f.read()

    print(f"Baixando GTFS de {GTFS_URL}...")
    resp = requests.get(GTFS_URL, timeout=60)
    resp.raise_for_status()
    with open(cached, "wb") as f:
        f.write(resp.content)
    print(f"Cache salvo em {cached}")
    return resp.content


def read_csv(z: zipfile.ZipFile, filename: str) -> list[dict]:
    if filename not in z.namelist():
        print(f"  {filename} não encontrado, pulando")
        return []
    with z.open(filename) as f:
        text = f.read().decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))


def parse_date(val: str) -> date | None:
    if not val:
        return None
    val = val.strip()
    if len(val) == 8:
        return date(int(val[:4]), int(val[4:6]), int(val[6:8]))
    return None


def float_or_none(val: str) -> float | None:
    if not val or val.strip() == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def int_or_none(val: str) -> int | None:
    if not val or val.strip() == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def bool_or_none(val: str) -> bool | None:
    if not val or val.strip() == "":
        return None
    return val.strip() == "1"


def run_import(zip_path: str | None = None) -> None:
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        if zip_path:
            print(f"Lendo arquivo local: {zip_path}")
            with open(zip_path, "rb") as f:
                raw = f.read()
        else:
            raw = download_zip()

        z = zipfile.ZipFile(io.BytesIO(raw))

        # --- Agency ---
        rows = read_csv(z, "agency.txt")
        for row in rows:
            db.add(Agency(
                agency_id=row.get("agency_id", "") or "",
                agency_name=row.get("agency_name", ""),
                agency_url=row.get("agency_url", ""),
                agency_timezone=row.get("agency_timezone", ""),
                agency_lang=row.get("agency_lang", "pt"),
                agency_phone=row.get("agency_phone"),
            ))
        db.commit()
        print(f"  Importadas {len(rows)} agências")

        # --- Routes ---
        rows = read_csv(z, "routes.txt")
        agency_map = {a.agency_id: a.id for a in db.query(Agency).all()}
        for row in rows:
            aid = row.get("agency_id", "")
            color = row.get("route_color", "").strip()
            db.add(Route(
                agency_id=agency_map.get(aid),
                route_id=row["route_id"],
                route_short_name=row.get("route_short_name", ""),
                route_long_name=row.get("route_long_name", ""),
                route_type=int(row.get("route_type", 3)),
                route_color=color or None,
                route_text_color=row.get("route_text_color", "").strip() or None,
                route_sort_order=int_or_none(row.get("route_sort_order")),
            ))
        db.commit()
        print(f"  Importadas {len(rows)} rotas")

        # --- Stops ---
        rows = read_csv(z, "stops.txt")
        batch = []
        for row in rows:
            batch.append(Stop(
                stop_id=row["stop_id"],
                stop_code=row.get("stop_code", "") or None,
                stop_name=row.get("stop_name", ""),
                stop_desc=row.get("stop_desc", "") or None,
                stop_lat=float_or_none(row.get("stop_lat")),
                stop_lon=float_or_none(row.get("stop_lon")),
                location_type=int_or_none(row.get("location_type")),
                parent_station=row.get("parent_station", "") or "",
                wheelchair_boarding=int_or_none(row.get("wheelchair_boarding")),
            ))
        db.bulk_save_objects(batch)
        db.commit()
        print(f"  Importadas {len(batch)} paradas")

        # --- Calendar ---
        rows = read_csv(z, "calendar.txt")
        batch = []
        for row in rows:
            batch.append(Calendar(
                service_id=row["service_id"],
                monday=row.get("monday", "0") == "1",
                tuesday=row.get("tuesday", "0") == "1",
                wednesday=row.get("wednesday", "0") == "1",
                thursday=row.get("thursday", "0") == "1",
                friday=row.get("friday", "0") == "1",
                saturday=row.get("saturday", "0") == "1",
                sunday=row.get("sunday", "0") == "1",
                start_date=parse_date(row.get("start_date", "")),
                end_date=parse_date(row.get("end_date", "")),
            ))
        db.bulk_save_objects(batch)
        db.commit()
        print(f"  Importados {len(batch)} calendários")

        # --- Calendar Dates ---
        rows = read_csv(z, "calendar_dates.txt")
        if rows:
            batch = []
            for row in rows:
                batch.append(CalendarDate(
                    service_id=row["service_id"],
                    date=parse_date(row.get("date", "")),
                    exception_type=int(row.get("exception_type", 1)),
                ))
            db.bulk_save_objects(batch)
            db.commit()
            print(f"  Importadas {len(batch)} exceções de calendário")

        # --- Trips ---
        rows = read_csv(z, "trips.txt")
        route_map = {r.route_id: r.id for r in db.query(Route).all()}
        service_map = {c.service_id: c.id for c in db.query(Calendar).all()}
        batch = []
        for row in rows:
            batch.append(Trip(
                route_id=route_map.get(row.get("route_id", "")),
                service_id=service_map.get(row.get("service_id", "")),
                service_ref=row.get("service_id", ""),
                trip_id=row["trip_id"],
                trip_headsign=row.get("trip_headsign", "") or None,
                trip_short_name=row.get("trip_short_name", "") or None,
                direction_id=int_or_none(row.get("direction_id")),
                block_id=row.get("block_id", "") or None,
                shape_id=row.get("shape_id", "") or None,
                wheelchair_accessible=int(row.get("wheelchair_accessible", 0)),
                bikes_allowed=int(row.get("bikes_allowed", 0)),
            ))
        db.bulk_save_objects(batch)
        db.commit()
        print(f"  Importadas {len(batch)} viagens")

        # --- Stop Times ---
        rows = read_csv(z, "stop_times.txt")
        trip_map = {t.trip_id: t.id for t in db.query(Trip).all()}
        stop_map = {s.stop_id: s.id for s in db.query(Stop).all()}
        batch = []
        count = 0
        for row in rows:
            if count % 50000 == 0 and count > 0:
                db.bulk_save_objects(batch)
                db.commit()
                batch = []
                print(f"  Importados {count} horários...")
            batch.append(StopTime(
                trip_id=trip_map.get(row.get("trip_id", "")),
                stop_id=stop_map.get(row.get("stop_id", "")),
                arrival_time=row.get("arrival_time", "") or None,
                departure_time=row.get("departure_time", "") or None,
                stop_sequence=int(row.get("stop_sequence", 0)),
                pickup_type=int(row.get("pickup_type", 0)),
                drop_off_type=int(row.get("drop_off_type", 0)),
                shape_dist_traveled=float_or_none(row.get("shape_dist_traveled")),
                timepoint=bool_or_none(row.get("timepoint")),
            ))
            count += 1
        if batch:
            db.bulk_save_objects(batch)
            db.commit()
        print(f"  Importados {count} horários")

        # --- Shapes ---
        rows = read_csv(z, "shapes.txt")
        if rows:
            batch = []
            for row in rows:
                batch.append(Shape(
                    shape_id=row["shape_id"],
                    shape_pt_lat=float(row.get("shape_pt_lat", 0)),
                    shape_pt_lon=float(row.get("shape_pt_lon", 0)),
                    shape_pt_sequence=int(row.get("shape_pt_sequence", 0)),
                    shape_dist_traveled=float_or_none(row.get("shape_dist_traveled")),
                ))
            db.bulk_save_objects(batch)
            db.commit()
            print(f"  Importados {len(batch)} pontos de shape")
        else:
            print("  shapes.txt não encontrado, pulando")

        z.close()
        print("Importação concluída com sucesso!")

    finally:
        db.close()


if __name__ == "__main__":
    run_import()
