from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import Route, Stop

router = APIRouter(prefix="/api")


@router.get("/search")
def search(q: str = Query(...), db: Session = Depends(get_db)):
    if not q.strip():
        return {"routes": [], "stops": []}

    routes = (
        db.query(Route)
        .filter(
            or_(
                Route.route_short_name.ilike(f"%{q}%"),
                Route.route_long_name.ilike(f"%{q}%"),
            )
        )
        .limit(10)
        .all()
    )

    stops = (
        db.query(Stop)
        .filter(Stop.stop_name.ilike(f"%{q}%"))
        .limit(10)
        .all()
    )

    return {
        "routes": [
            {
                "route_id": r.route_id,
                "short_name": r.route_short_name or "",
                "long_name": r.route_long_name or "",
                "color": f"#{r.route_color or '999999'}",
            }
            for r in routes
        ],
        "stops": [
            {
                "stop_id": s.stop_id,
                "stop_name": s.stop_name,
                "stop_lat": float(s.stop_lat) if s.stop_lat else None,
                "stop_lon": float(s.stop_lon) if s.stop_lon else None,
            }
            for s in stops
        ],
    }
