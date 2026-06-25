import csv
import io
import os
import zipfile
from datetime import date, datetime

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Feed, Agency, Route, Stop, Trip, StopTime,
    Shape, Calendar, CalendarDate,
)


class Command(BaseCommand):
    help = 'Download and import GTFS data from URBS Curitiba'

    GTFS_URL = 'http://files.urbs.curitiba.pr.gov.br/google/google_transit.zip'

    def add_arguments(self, parser):
        parser.add_argument('--zip', type=str, help='Path to local zip file')
        parser.add_argument('--skip-download', action='store_true', help='Skip download, use cached zip')

    def handle(self, *args, **options):
        zip_path = options.get('zip')

        if zip_path:
            self.stdout.write(f'Reading local file: {zip_path}')
            with open(zip_path, 'rb') as f:
                raw = f.read()
        else:
            cached = os.path.join('feeds', 'google_transit.zip')
            if options.get('skip_download') and os.path.exists(cached):
                self.stdout.write('Using cached zip...')
                with open(cached, 'rb') as f:
                    raw = f.read()
            else:
                self.stdout.write(f'Downloading GTFS from {self.GTFS_URL}...')
                resp = requests.get(self.GTFS_URL, timeout=60)
                resp.raise_for_status()
                raw = resp.content
                os.makedirs('feeds', exist_ok=True)
                with open(cached, 'wb') as f:
                    f.write(raw)
                self.stdout.write(f'Cached to {cached}')

        with transaction.atomic():
            feed = Feed.objects.create(
                name='URBS Curitiba',
                url=self.GTFS_URL,
            )
            self.stdout.write(f'Created feed #{feed.id}')

            z = zipfile.ZipFile(io.BytesIO(raw))

            self._import_agency(z, feed)
            self._import_routes(z, feed)
            self._import_stops(z, feed)
            self._import_calendar(z, feed)
            self._import_calendar_dates(z, feed)
            self._import_trips(z, feed)
            self._import_stop_times(z, feed)
            self._import_shapes(z, feed)

            z.close()

        self.stdout.write(self.style.SUCCESS(f'Feed #{feed.id} imported successfully!'))

    def _read_csv(self, z, filename):
        if filename not in z.namelist():
            self.stdout.write(self.style.WARNING(f'{filename} not found, skipping'))
            return []
        with z.open(filename) as f:
            text = f.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(text))
            return list(reader)

    def _import_agency(self, z, feed):
        rows = self._read_csv(z, 'agency.txt')
        for row in rows:
            Agency.objects.create(
                feed=feed,
                agency_id=row.get('agency_id', '') or '',
                agency_name=row.get('agency_name', ''),
                agency_url=row.get('agency_url', ''),
                agency_timezone=row.get('agency_timezone', ''),
                agency_lang=row.get('agency_lang', 'pt'),
                agency_phone=row.get('agency_phone'),
            )
        self.stdout.write(f'  Imported {len(rows)} agencies')

    def _import_routes(self, z, feed):
        rows = self._read_csv(z, 'routes.txt')
        agency_map = {a.agency_id: a for a in Agency.objects.filter(feed=feed)}
        for row in rows:
            aid = row.get('agency_id', '')
            color = row.get('route_color', '').strip()
            if color and not color.startswith('#'):
                pass
            text_color = row.get('route_text_color', '').strip() or None
            Route.objects.create(
                feed=feed,
                agency=agency_map.get(aid),
                route_id=row['route_id'],
                route_short_name=row.get('route_short_name', ''),
                route_long_name=row.get('route_long_name', ''),
                route_type=int(row.get('route_type', 3)),
                route_color=color or None,
                route_text_color=text_color,
                route_sort_order=self._int_or_none(row.get('route_sort_order')),
            )
        self.stdout.write(f'  Imported {len(rows)} routes')

    def _import_stops(self, z, feed):
        rows = self._read_csv(z, 'stops.txt')
        batch = []
        for row in rows:
            batch.append(Stop(
                feed=feed,
                stop_id=row['stop_id'],
                stop_code=row.get('stop_code', '') or None,
                stop_name=row.get('stop_name', ''),
                stop_desc=row.get('stop_desc', '') or None,
                stop_lat=self._float_or_none(row.get('stop_lat')),
                stop_lon=self._float_or_none(row.get('stop_lon')),
                location_type=self._int_or_none(row.get('location_type')),
                parent_station=row.get('parent_station', '') or '',
                wheelchair_boarding=self._int_or_none(row.get('wheelchair_boarding')),
            ))
        Stop.objects.bulk_create(batch, batch_size=500)
        self.stdout.write(f'  Imported {len(batch)} stops')

    def _import_calendar(self, z, feed):
        rows = self._read_csv(z, 'calendar.txt')
        batch = []
        for row in rows:
            batch.append(Calendar(
                feed=feed,
                service_id=row['service_id'],
                monday=row.get('monday', '0') == '1',
                tuesday=row.get('tuesday', '0') == '1',
                wednesday=row.get('wednesday', '0') == '1',
                thursday=row.get('thursday', '0') == '1',
                friday=row.get('friday', '0') == '1',
                saturday=row.get('saturday', '0') == '1',
                sunday=row.get('sunday', '0') == '1',
                start_date=self._parse_date(row.get('start_date', '')),
                end_date=self._parse_date(row.get('end_date', '')),
            ))
        Calendar.objects.bulk_create(batch, batch_size=500)
        self.stdout.write(f'  Imported {len(batch)} calendars')

    def _import_calendar_dates(self, z, feed):
        rows = self._read_csv(z, 'calendar_dates.txt')
        if not rows:
            return
        batch = []
        for row in rows:
            batch.append(CalendarDate(
                feed=feed,
                service_id=row['service_id'],
                date=self._parse_date(row.get('date', '')),
                exception_type=int(row.get('exception_type', 1)),
            ))
        CalendarDate.objects.bulk_create(batch, batch_size=500)
        self.stdout.write(f'  Imported {len(batch)} calendar dates')

    def _import_trips(self, z, feed):
        rows = self._read_csv(z, 'trips.txt')
        route_map = {r.route_id: r for r in Route.objects.filter(feed=feed)}
        service_map = {c.service_id: c for c in Calendar.objects.filter(feed=feed)}
        batch = []
        for row in rows:
            batch.append(Trip(
                feed=feed,
                route=route_map.get(row.get('route_id', '')),
                service=service_map.get(row.get('service_id', '')),
                service_ref=row.get('service_id', ''),
                trip_id=row['trip_id'],
                trip_headsign=row.get('trip_headsign', '') or None,
                trip_short_name=row.get('trip_short_name', '') or None,
                direction_id=self._int_or_none(row.get('direction_id')),
                block_id=row.get('block_id', '') or None,
                shape_id=row.get('shape_id', '') or None,
                wheelchair_accessible=int(row.get('wheelchair_accessible', 0)),
                bikes_allowed=int(row.get('bikes_allowed', 0)),
            ))
        Trip.objects.bulk_create(batch, batch_size=500)
        self.stdout.write(f'  Imported {len(batch)} trips')

    def _import_stop_times(self, z, feed):
        rows = self._read_csv(z, 'stop_times.txt')
        trip_map = {t.trip_id: t for t in Trip.objects.filter(feed=feed)}
        stop_map = {s.stop_id: s for s in Stop.objects.filter(feed=feed)}
        batch = []
        count = 0
        for row in rows:
            if count % 50000 == 0 and count > 0:
                StopTime.objects.bulk_create(batch, batch_size=500)
                batch = []
                self.stdout.write(f'  Imported {count} stop times...')
            batch.append(StopTime(
                feed=feed,
                trip=trip_map.get(row.get('trip_id', '')),
                stop=stop_map.get(row.get('stop_id', '')),
                arrival_time=row.get('arrival_time', '') or None,
                departure_time=row.get('departure_time', '') or None,
                stop_sequence=int(row.get('stop_sequence', 0)),
                pickup_type=int(row.get('pickup_type', 0)),
                drop_off_type=int(row.get('drop_off_type', 0)),
                shape_dist_traveled=self._float_or_none(row.get('shape_dist_traveled')),
                timepoint=self._bool_or_none(row.get('timepoint')),
            ))
            count += 1
        if batch:
            StopTime.objects.bulk_create(batch, batch_size=500)
        self.stdout.write(f'  Imported {count} stop times')

    def _import_shapes(self, z, feed):
        rows = self._read_csv(z, 'shapes.txt')
        if not rows:
            self.stdout.write(self.style.WARNING('  shapes.txt not found, skipping'))
            return
        batch = []
        for row in rows:
            batch.append(Shape(
                feed=feed,
                shape_id=row['shape_id'],
                shape_pt_lat=float(row.get('shape_pt_lat', 0)),
                shape_pt_lon=float(row.get('shape_pt_lon', 0)),
                shape_pt_sequence=int(row.get('shape_pt_sequence', 0)),
                shape_dist_traveled=self._float_or_none(row.get('shape_dist_traveled')),
            ))
        Shape.objects.bulk_create(batch, batch_size=500)
        self.stdout.write(f'  Imported {len(batch)} shape points')

    def _parse_date(self, val):
        if not val:
            return None
        val = val.strip()
        if len(val) == 8:
            return date(int(val[:4]), int(val[4:6]), int(val[6:8]))
        return None

    def _float_or_none(self, val):
        if not val or val.strip() == '':
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _int_or_none(self, val):
        if not val or val.strip() == '':
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    def _bool_or_none(self, val):
        if not val or val.strip() == '':
            return None
        return val.strip() == '1'
