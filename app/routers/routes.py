from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Route, Trip, StopTime, Stop, Shape, Calendar
from ..schemas import RouteOut, RouteDetailOut, ShapePoint

router = APIRouter(prefix="/api")


@router.get("/routes")
def list_routes(
    mode: int | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Route).join(Route.agency)

    if mode is not None:
        query = query.filter(Route.route_type == mode)

    if q:
        query = query.filter(Route.route_short_name.ilike(f"%{q}%"))

    routes = query.order_by(Route.route_sort_order, Route.route_short_name).all()

    return {
        "features": [
            {
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "id": r.id,
                    "route_id": r.route_id,
                    "short_name": r.route_short_name or "",
                    "long_name": r.route_long_name or "",
                    "route_type": r.route_type,
                    "color": f"#{r.route_color or '999999'}",
                    "text_color": f"#{r.route_text_color or 'FFFFFF'}",
                },
            }
            for r in routes
        ]
    }


@router.get("/routes/{route_id}")
def route_detail(route_id: str, db: Session = Depends(get_db)):
    route = db.query(Route).join(Route.agency).filter(Route.route_id == route_id).first()
    if not route:
        return {"error": "Route not found"}, 404

    trip = db.query(Trip).filter(Trip.route_id == route.id).first()
    days = []
    if trip and trip.service:
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if getattr(trip.service, day):
                days.append(day)

    return {
        "route_id": route.route_id,
        "short_name": route.route_short_name or "",
        "long_name": route.route_long_name or "",
        "route_type": route.route_type,
        "color": f"#{route.route_color or '999999'}",
        "text_color": f"#{route.route_text_color or 'FFFFFF'}",
        "agency": route.agency.agency_name if route.agency else "",
        "operating_days": days,
    }


@router.get("/routes/{route_id}/shape")
def route_shape(route_id: str, db: Session = Depends(get_db)):
    trips = (
        db.query(Trip)
        .join(Route)
        .filter(Route.route_id == route_id, Trip.shape_id.isnot(None), Trip.shape_id != "")
        .all()
    )
    shape_ids = list(set(t.shape_id for t in trips))[:4]

    if not shape_ids:
        return {"type": "FeatureCollection", "features": []}

    shapes = (
        db.query(Shape)
        .filter(Shape.shape_id.in_(shape_ids))
        .order_by(Shape.shape_id, Shape.shape_pt_sequence)
        .all()
    )

    coords_map: dict[str, list[list[float]]] = {}
    for s in shapes:
        coords_map.setdefault(s.shape_id, []).append([s.shape_pt_lon, s.shape_pt_lat])

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {"shape_id": sid},
            }
            for sid, coords in coords_map.items()
        ],
    }


@router.get("/routes/{route_id}/stops")
def route_stops(route_id: str, db: Session = Depends(get_db)):
    route = db.query(Route).filter(Route.route_id == route_id).first()
    if not route:
        return {"error": "Route not found"}, 404

    trips = db.query(Trip).filter(Trip.route_id == route.id).limit(5).all()
    trip_ids = [t.id for t in trips]

    stop_times = (
        db.query(StopTime)
        .filter(StopTime.trip_id.in_(trip_ids))
        .join(Stop, StopTime.stop_id == Stop.id)
        .order_by(StopTime.stop_sequence)
        .all()
    )

    seen: set[int] = set()
    result = []
    for st in stop_times:
        if st.stop_id not in seen and st.stop:
            seen.add(st.stop_id)
            result.append({
                "stop_id": st.stop.stop_id,
                "stop_name": st.stop.stop_name,
                "stop_lat": float(st.stop.stop_lat) if st.stop.stop_lat else None,
                "stop_lon": float(st.stop.stop_lon) if st.stop.stop_lon else None,
                "stop_sequence": st.stop_sequence,
            })

    return {"stops": result}
