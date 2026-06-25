from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Stop, StopTime, Trip, Calendar, Route

router = APIRouter(prefix="/api")


@router.get("/stops")
def list_stops(bbox: str | None = Query(None), db: Session = Depends(get_db)):
    query = db.query(Stop)

    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) == 4:
                min_lon, min_lat, max_lon, max_lat = parts
                query = query.filter(
                    Stop.stop_lat >= min_lat,
                    Stop.stop_lat <= max_lat,
                    Stop.stop_lon >= min_lon,
                    Stop.stop_lon <= max_lon,
                )
        except ValueError:
            pass

    stops = query.all()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(s.stop_lon), float(s.stop_lat)],
                },
                "properties": {
                    "id": s.id,
                    "stop_id": s.stop_id,
                    "stop_name": s.stop_name,
                    "stop_code": s.stop_code or "",
                },
            }
            for s in stops
            if s.stop_lat and s.stop_lon
        ],
    }


@router.get("/stops/{stop_id}")
def stop_detail(stop_id: str, db: Session = Depends(get_db)):
    stop = db.query(Stop).filter(Stop.stop_id == stop_id).first()
    if not stop:
        return {"error": "Stop not found"}, 404

    return {
        "stop_id": stop.stop_id,
        "stop_name": stop.stop_name,
        "stop_code": stop.stop_code or "",
        "stop_lat": float(stop.stop_lat) if stop.stop_lat else None,
        "stop_lon": float(stop.stop_lon) if stop.stop_lon else None,
    }


@router.get("/stops/{stop_id}/times")
def stop_times(stop_id: str, db: Session = Depends(get_db)):
    today = date.today()
    weekday = today.weekday()
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    today_name = day_names[weekday]

    calendars = db.query(Calendar).filter(getattr(Calendar, today_name) == True).all()
    service_ids = [c.service_id for c in calendars]

    stop = db.query(Stop).filter(Stop.stop_id == stop_id).first()
    if not stop:
        return {"error": "Stop not found"}, 404

    stop_times = (
        db.query(StopTime)
        .filter(StopTime.stop_id == stop.id, Trip.service_ref.in_(service_ids))
        .join(Trip)
        .join(Route, Trip.route_id == Route.id)
        .order_by(StopTime.departure_time)
        .limit(50)
        .all()
    )

    return {
        "times": [
            {
                "trip_id": st.trip.trip_id,
                "route_short_name": st.trip.route.route_short_name if st.trip.route else "",
                "route_color": f"#{st.trip.route.route_color or '999999'}" if st.trip.route else "#999999",
                "arrival_time": st.arrival_time or "",
                "departure_time": st.departure_time or "",
                "stop_sequence": st.stop_sequence,
                "headsign": st.trip.trip_headsign or "",
            }
            for st in stop_times
        ],
        "day": today_name,
    }
