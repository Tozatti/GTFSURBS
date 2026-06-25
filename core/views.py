import json
from datetime import date, datetime

from django.http import JsonResponse
from django.shortcuts import render

from .models import Route, Stop, Trip, StopTime, Shape, Calendar


def index(request):
    return render(request, 'core/index.html')


def _json_serializer(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError


def api_routes(request):
    routes = Route.objects.select_related('agency').all()

    mode_filter = request.GET.get('mode')
    if mode_filter:
        routes = routes.filter(route_type=mode_filter)

    search = request.GET.get('q', '').strip()
    if search:
        routes = routes.filter(route_short_name__icontains=search)

    features = []
    for r in routes:
        color = r.route_color or '999999'
        text_color = r.route_text_color or 'FFFFFF'
        features.append({
            'type': 'Feature',
            'geometry': None,
            'properties': {
                'id': r.id,
                'route_id': r.route_id,
                'short_name': r.route_short_name or '',
                'long_name': r.route_long_name or '',
                'route_type': r.route_type,
                'color': f'#{color}',
                'text_color': f'#{text_color}',
            }
        })

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': features,
    })


def api_route_detail(request, route_id):
    try:
        route = Route.objects.select_related('agency').get(route_id=route_id)
    except Route.DoesNotExist:
        return JsonResponse({'error': 'Route not found'}, status=404)

    trip = Trip.objects.filter(route=route).select_related('service').first()
    days = []
    if trip and trip.service:
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            if getattr(trip.service, day):
                days.append(day)

    return JsonResponse({
        'route_id': route.route_id,
        'short_name': route.route_short_name or '',
        'long_name': route.route_long_name or '',
        'route_type': route.route_type,
        'color': f'#{route.route_color or "999999"}',
        'text_color': f'#{route.route_text_color or "FFFFFF"}',
        'agency': route.agency.agency_name if route.agency else '',
        'operating_days': days,
    })


def api_route_shape(request, route_id):
    trips = Trip.objects.filter(route__route_id=route_id).exclude(shape_id__isnull=True).exclude(shape_id='')
    shape_ids = list(set(trips.values_list('shape_id', flat=True)[:4]))

    if not shape_ids:
        return JsonResponse({'type': 'FeatureCollection', 'features': []})

    shapes = Shape.objects.filter(shape_id__in=shape_ids).order_by('shape_pt_sequence')
    coords_map = {}
    for s in shapes:
        coords_map.setdefault(s.shape_id, []).append([s.shape_pt_lon, s.shape_pt_lat])

    features = []
    for sid, coords in coords_map.items():
        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': coords,
            },
            'properties': {
                'shape_id': sid,
            }
        })

    return JsonResponse({'type': 'FeatureCollection', 'features': features})


def api_route_stops(request, route_id):
    route = Route.objects.get(route_id=route_id)
    trips = Trip.objects.filter(route=route)[:5]
    trip_pks = list(trips.values_list('id', flat=True))

    stop_times = StopTime.objects.filter(
        trip_id__in=trip_pks
    ).select_related('stop').order_by('stop_sequence')

    seen = {}
    result = []
    for st in stop_times:
        if st.stop_id not in seen:
            seen[st.stop_id] = True
            result.append({
                'stop_id': st.stop.stop_id if st.stop else st.stop_id,
                'stop_name': st.stop.stop_name if st.stop else '',
                'stop_lat': float(st.stop.stop_lat) if st.stop and st.stop.stop_lat else None,
                'stop_lon': float(st.stop.stop_lon) if st.stop and st.stop.stop_lon else None,
                'stop_sequence': st.stop_sequence,
            })

    return JsonResponse({'stops': result})


def api_stops(request):
    stops = Stop.objects.all()
    bbox = request.GET.get('bbox')
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(',')]
            if len(parts) == 4:
                min_lon, min_lat, max_lon, max_lat = parts
                stops = stops.filter(
                    stop_lat__gte=min_lat, stop_lat__lte=max_lat,
                    stop_lon__gte=min_lon, stop_lon__lte=max_lon,
                )
        except ValueError:
            pass

    features = []
    for s in stops:
        if s.stop_lat and s.stop_lon:
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(s.stop_lon), float(s.stop_lat)],
                },
                'properties': {
                    'id': s.id,
                    'stop_id': s.stop_id,
                    'stop_name': s.stop_name,
                    'stop_code': s.stop_code or '',
                }
            })

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': features,
    })


def api_stop_detail(request, stop_id):
    try:
        stop = Stop.objects.get(stop_id=stop_id)
    except Stop.DoesNotExist:
        return JsonResponse({'error': 'Stop not found'}, status=404)

    return JsonResponse({
        'stop_id': stop.stop_id,
        'stop_name': stop.stop_name,
        'stop_code': stop.stop_code or '',
        'stop_lat': float(stop.stop_lat) if stop.stop_lat else None,
        'stop_lon': float(stop.stop_lon) if stop.stop_lon else None,
    })


def api_stop_times(request, stop_id):
    today = date.today()
    weekday = today.weekday()
    day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    today_name = day_names[weekday]

    calendars = Calendar.objects.filter(**{today_name: True})
    service_ids = list(calendars.values_list('service_id', flat=True))

    stop_times = StopTime.objects.filter(
        stop__stop_id=stop_id,
        trip__service_ref__in=service_ids,
    ).select_related('trip__route').order_by('departure_time')[:50]

    result = []
    for st in stop_times:
        result.append({
            'trip_id': st.trip.trip_id,
            'route_short_name': st.trip.route.route_short_name if st.trip.route else '',
            'route_color': f'#{st.trip.route.route_color or "999999"}' if st.trip.route else '#999999',
            'arrival_time': st.arrival_time or '',
            'departure_time': st.departure_time or '',
            'stop_sequence': st.stop_sequence,
            'headsign': st.trip.trip_headsign or '',
        })

    return JsonResponse({'times': result, 'day': today_name})


def api_search(request):
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'routes': [], 'stops': []})

    routes = Route.objects.filter(
        route_short_name__icontains=q
    ) | Route.objects.filter(route_long_name__icontains=q)
    routes = routes.distinct()[:10]

    stops = Stop.objects.filter(stop_name__icontains=q)[:10]

    return JsonResponse({
        'routes': [
            {
                'route_id': r.route_id,
                'short_name': r.route_short_name or '',
                'long_name': r.route_long_name or '',
                'color': f'#{r.route_color or "999999"}',
            }
            for r in routes
        ],
        'stops': [
            {
                'stop_id': s.stop_id,
                'stop_name': s.stop_name,
                'stop_lat': float(s.stop_lat) if s.stop_lat else None,
                'stop_lon': float(s.stop_lon) if s.stop_lon else None,
            }
            for s in stops
        ],
    })
