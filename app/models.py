from sqlalchemy import Column, Integer, String, Float, Boolean, Date, ForeignKey, Index
from sqlalchemy.orm import relationship
from .database import Base


class Agency(Base):
    __tablename__ = "agencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_id = Column(String(255), default="")
    agency_name = Column(String(255), nullable=False)
    agency_url = Column(String(500), nullable=False)
    agency_timezone = Column(String(255), nullable=False)
    agency_lang = Column(String(2), default="pt")
    agency_phone = Column(String(127), nullable=True)


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_id = Column(Integer, ForeignKey("agencies.id"), nullable=True)
    route_id = Column(String(255), index=True, nullable=False)
    route_short_name = Column(String(63), index=True, nullable=True)
    route_long_name = Column(String(255), nullable=True)
    route_type = Column(Integer, default=3)
    route_color = Column(String(6), nullable=True)
    route_text_color = Column(String(6), nullable=True)
    route_sort_order = Column(Integer, nullable=True)

    agency = relationship("Agency", backref="routes")


class Stop(Base):
    __tablename__ = "stops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stop_id = Column(String(255), index=True, nullable=False)
    stop_code = Column(String(255), nullable=True)
    stop_name = Column(String(255), index=True, nullable=False)
    stop_desc = Column(String, nullable=True)
    stop_lat = Column(Float, nullable=True)
    stop_lon = Column(Float, nullable=True)
    location_type = Column(Integer, nullable=True)
    parent_station = Column(String(255), default="")
    wheelchair_boarding = Column(Integer, nullable=True)


class Calendar(Base):
    __tablename__ = "calendars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(String(255), index=True, nullable=False)
    monday = Column(Boolean, nullable=False)
    tuesday = Column(Boolean, nullable=False)
    wednesday = Column(Boolean, nullable=False)
    thursday = Column(Boolean, nullable=False)
    friday = Column(Boolean, nullable=False)
    saturday = Column(Boolean, nullable=False)
    sunday = Column(Boolean, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)


class CalendarDate(Base):
    __tablename__ = "calendar_dates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(String(255), index=True, nullable=False)
    date = Column(Date, nullable=False)
    exception_type = Column(Integer, nullable=False)


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)
    service_id = Column(Integer, ForeignKey("calendars.id"), nullable=True)
    service_ref = Column(String(255), index=True, default="")
    trip_id = Column(String(255), index=True, nullable=False)
    trip_headsign = Column(String(255), nullable=True)
    trip_short_name = Column(String(255), nullable=True)
    direction_id = Column(Integer, nullable=True)
    block_id = Column(String(255), nullable=True)
    shape_id = Column(String(255), index=True, nullable=True)
    wheelchair_accessible = Column(Integer, default=0)
    bikes_allowed = Column(Integer, default=0)

    route = relationship("Route", backref="trips")
    service = relationship("Calendar", backref="trips")


class StopTime(Base):
    __tablename__ = "stop_times"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=True)
    arrival_time = Column(String(8), index=True, nullable=True)
    departure_time = Column(String(8), nullable=True)
    stop_sequence = Column(Integer, nullable=False)
    pickup_type = Column(Integer, default=0)
    drop_off_type = Column(Integer, default=0)
    shape_dist_traveled = Column(Float, nullable=True)
    timepoint = Column(Boolean, nullable=True)

    trip = relationship("Trip", backref="stop_times")
    stop = relationship("Stop", backref="stop_times")

    __table_args__ = (
        Index("ix_stop_times_trip_seq", "trip_id", "stop_sequence"),
    )


class Shape(Base):
    __tablename__ = "shapes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shape_id = Column(String(255), index=True, nullable=False)
    shape_pt_lat = Column(Float, nullable=False)
    shape_pt_lon = Column(Float, nullable=False)
    shape_pt_sequence = Column(Integer, nullable=False)
    shape_dist_traveled = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_shapes_id_seq", "shape_id", "shape_pt_sequence"),
    )
