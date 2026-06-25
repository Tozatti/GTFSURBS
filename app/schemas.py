from datetime import date
from typing import Optional
from pydantic import BaseModel


class RouteOut(BaseModel):
    id: int
    route_id: str
    short_name: str
    long_name: str
    route_type: int
    color: str
    text_color: str
    agency_name: str

    class Config:
        from_attributes = True


class RouteDetailOut(BaseModel):
    route_id: str
    short_name: str
    long_name: str
    route_type: int
    color: str
    text_color: str
    agency_name: str
    operating_days: list[str]


class StopOut(BaseModel):
    id: int
    stop_id: str
    stop_name: str
    stop_code: str
    stop_lat: Optional[float] = None
    stop_lon: Optional[float] = None

    class Config:
        from_attributes = True


class StopDetailOut(BaseModel):
    stop_id: str
    stop_name: str
    stop_code: str
    stop_lat: Optional[float] = None
    stop_lon: Optional[float] = None


class StopTimeOut(BaseModel):
    trip_id: str
    route_short_name: str
    route_color: str
    arrival_time: str
    departure_time: str
    stop_sequence: int
    headsign: str


class ShapePoint(BaseModel):
    lat: float
    lon: float


class SearchResult(BaseModel):
    routes: list[dict]
    stops: list[dict]
