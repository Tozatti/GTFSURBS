#!/usr/bin/env python3
"""Validador GTFS conforme especificação oficial (https://gtfs.org/documentation/schedule/reference/)."""

import csv
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

GTFS_DIR = os.path.join(os.path.dirname(__file__), "GTFS")

REQUIRED_FILES = ["agency.txt", "routes.txt", "trips.txt", "stop_times.txt", "stops.txt", "calendar.txt", "calendar_dates.txt"]

FILE_SPECS = {
    "agency.txt": {
        "required": True,
        "fields": {
            "agency_id": {"required": True, "type": "text"},
            "agency_name": {"required": True, "type": "text"},
            "agency_url": {"required": True, "type": "url"},
            "agency_timezone": {"required": True, "type": "timezone"},
            "agency_lang": {"required": False, "type": "lang"},
            "agency_phone": {"required": False, "type": "phone"},
            "agency_fare_url": {"required": False, "type": "url"},
            "agency_email": {"required": False, "type": "email"},
        },
        "unique": ["agency_id"],
    },
    "routes.txt": {
        "required": True,
        "fields": {
            "route_id": {"required": True, "type": "text"},
            "agency_id": {"required": False, "type": "text"},
            "route_short_name": {"required": False, "type": "text"},
            "route_long_name": {"required": False, "type": "text"},
            "route_desc": {"required": False, "type": "text"},
            "route_type": {"required": True, "type": "route_type"},
            "route_url": {"required": False, "type": "url"},
            "route_color": {"required": False, "type": "color"},
            "route_text_color": {"required": False, "type": "color"},
            "route_sort_order": {"required": False, "type": "non_neg_int"},
            "continuous_pickup": {"required": False, "type": "enum", "values": ["0", "1", "2", "3"]},
            "continuous_drop_off": {"required": False, "type": "enum", "values": ["0", "1", "2", "3"]},
        },
        "unique": ["route_id"],
        "require_one_of": ["route_short_name", "route_long_name"],
    },
    "stops.txt": {
        "required": True,
        "fields": {
            "stop_id": {"required": True, "type": "text"},
            "stop_code": {"required": False, "type": "text"},
            "stop_name": {"required": True, "type": "text"},
            "stop_desc": {"required": False, "type": "text"},
            "stop_lat": {"required": True, "type": "lat"},
            "stop_lon": {"required": True, "type": "lon"},
            "zone_id": {"required": False, "type": "text"},
            "stop_url": {"required": False, "type": "url"},
            "location_type": {"required": False, "type": "enum", "values": ["", "0", "1", "2", "3", "4"]},
            "parent_station": {"required": False, "type": "text"},
            "stop_timezone": {"required": False, "type": "timezone"},
            "wheelchair_boarding": {"required": False, "type": "enum", "values": ["", "0", "1", "2"]},
            "level_id": {"required": False, "type": "text"},
            "platform_code": {"required": False, "type": "text"},
        },
        "unique": ["stop_id"],
    },
    "calendar.txt": {
        "required": True,
        "fields": {
            "service_id": {"required": True, "type": "text"},
            "monday": {"required": True, "type": "binary"},
            "tuesday": {"required": True, "type": "binary"},
            "wednesday": {"required": True, "type": "binary"},
            "thursday": {"required": True, "type": "binary"},
            "friday": {"required": True, "type": "binary"},
            "saturday": {"required": True, "type": "binary"},
            "sunday": {"required": True, "type": "binary"},
            "start_date": {"required": True, "type": "date"},
            "end_date": {"required": True, "type": "date"},
        },
        "unique": ["service_id"],
    },
    "calendar_dates.txt": {
        "required": True,
        "fields": {
            "service_id": {"required": True, "type": "text"},
            "date": {"required": True, "type": "date"},
            "exception_type": {"required": True, "type": "enum", "values": ["1", "2"]},
        },
        "unique": ["service_id", "date"],
    },
    "trips.txt": {
        "required": True,
        "fields": {
            "route_id": {"required": True, "type": "text"},
            "service_id": {"required": True, "type": "text"},
            "trip_id": {"required": True, "type": "text"},
            "trip_headsign": {"required": False, "type": "text"},
            "trip_short_name": {"required": False, "type": "text"},
            "direction_id": {"required": False, "type": "enum", "values": ["", "0", "1"]},
            "block_id": {"required": False, "type": "text"},
            "shape_id": {"required": False, "type": "text"},
            "wheelchair_accessible": {"required": False, "type": "enum", "values": ["", "0", "1", "2"]},
            "bikes_allowed": {"required": False, "type": "enum", "values": ["", "0", "1", "2"]},
        },
        "unique": ["trip_id"],
    },
    "stop_times.txt": {
        "required": True,
        "fields": {
            "trip_id": {"required": True, "type": "text"},
            "arrival_time": {"required": True, "type": "time"},
            "departure_time": {"required": True, "type": "time"},
            "stop_id": {"required": True, "type": "text"},
            "stop_sequence": {"required": True, "type": "non_neg_int"},
            "stop_headsign": {"required": False, "type": "text"},
            "pickup_type": {"required": False, "type": "enum", "values": ["", "0", "1", "2", "3"]},
            "drop_off_type": {"required": False, "type": "enum", "values": ["", "0", "1", "2", "3"]},
            "continuous_pickup": {"required": False, "type": "enum", "values": ["", "0", "1", "2", "3"]},
            "continuous_drop_off": {"required": False, "type": "enum", "values": ["", "0", "1", "2", "3"]},
            "shape_dist_traveled": {"required": False, "type": "non_neg_float"},
            "timepoint": {"required": False, "type": "enum", "values": ["", "0", "1"]},
        },
        "unique": ["trip_id", "stop_sequence"],
        "sort_by": ["trip_id", "stop_sequence"],
    },
    "shapes.txt": {
        "required": False,
        "fields": {
            "shape_id": {"required": True, "type": "text"},
            "shape_pt_lat": {"required": True, "type": "lat"},
            "shape_pt_lon": {"required": True, "type": "lon"},
            "shape_pt_sequence": {"required": True, "type": "non_neg_int"},
            "shape_dist_traveled": {"required": False, "type": "non_neg_float"},
        },
        "unique": ["shape_id", "shape_pt_sequence"],
    },
    "transfers.txt": {
        "required": False,
        "fields": {
            "from_stop_id": {"required": True, "type": "text"},
            "to_stop_id": {"required": True, "type": "text"},
            "transfer_type": {"required": True, "type": "enum", "values": ["0", "1", "2", "3"]},
            "min_transfer_time": {"required": False, "type": "non_neg_int"},
        },
    },
    "feed_info.txt": {
        "required": False,
        "fields": {
            "feed_publisher_name": {"required": True, "type": "text"},
            "feed_publisher_url": {"required": True, "type": "url"},
            "feed_lang": {"required": True, "type": "lang"},
            "feed_start_date": {"required": False, "type": "date"},
            "feed_end_date": {"required": False, "type": "date"},
            "feed_version": {"required": False, "type": "text"},
            "feed_contact_email": {"required": False, "type": "email"},
            "feed_contact_url": {"required": False, "type": "url"},
        },
    },
}


def read_csv(filename):
    path = os.path.join(GTFS_DIR, filename)
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows, reader.fieldnames


errors = []
warnings = []


def err(filename, line, message):
    errors.append(f"[{filename}:{line}] {message}")


def warn(filename, line, message):
    warnings.append(f"[{filename}:{line}] {message}")


def validate_file_exists(filename):
    path = os.path.join(GTFS_DIR, filename)
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) == 0:
        err(filename, 0, "Arquivo vazio")
        return False
    return True


def validate_columns(filename, rows, fieldnames, spec):
    actual = set(fieldnames or [])

    # Only fields marked value-required must also have their column present
    expected_cols = {f for f, r in spec["fields"].items() if r.get("column_required", r["required"])}
    missing = expected_cols - actual
    extra = actual - set(spec["fields"].keys())

    for col in sorted(missing):
        err(filename, 1, f"Coluna obrigatória ausente: '{col}'")
    for col in sorted(extra):
        warn(filename, 1, f"Coluna não esperada: '{col}'")


def validate_row(filename, row, lineno, spec, refs=None):
    for field, rules in spec["fields"].items():
        val = row.get(field, "")
        is_required = rules["required"]
        ftype = rules["type"]

        if val == "" or val is None:
            if is_required:
                err(filename, lineno, f"Campo obrigatório '{field}' vazio")
            continue

        if ftype == "url":
            if val and str(val).strip() and not (val.startswith("http://") or val.startswith("https://")):
                warn(filename, lineno, f"'{field}' parece não ser URL válida: {val}")

        elif ftype == "date":
            if not re.match(r"^\d{8}$", val):
                err(filename, lineno, f"'{field}' não é data válida (YYYYMMDD): {val}")

        elif ftype == "time":
            if not re.match(r"^\d{2}:\d{2}:\d{2}$", val):
                err(filename, lineno, f"'{field}' não é hora válida (HH:MM:SS): {val}")

        elif ftype == "lat":
            try:
                lat = float(val)
                if lat < -90 or lat > 90:
                    err(filename, lineno, f"'{field}' latitude fora do intervalo [-90,90]: {val}")
            except ValueError:
                err(filename, lineno, f"'{field}' não é número: {val}")

        elif ftype == "lon":
            try:
                lon = float(val)
                if lon < -180 or lon > 180:
                    err(filename, lineno, f"'{field}' longitude fora do intervalo [-180,180]: {val}")
            except ValueError:
                err(filename, lineno, f"'{field}' não é número: {val}")

        elif ftype == "binary":
            if val not in ("0", "1"):
                err(filename, lineno, f"'{field}' deve ser 0 ou 1: {val}")

        elif ftype == "color":
            if val and not re.match(r"^[0-9A-Fa-f]{6}$", val):
                err(filename, lineno, f"'{field}' não é cor hexadecimal válida: {val}")

        elif ftype == "route_type":
            try:
                rt = int(val)
                if rt not in (0, 1, 2, 3, 4, 5, 6, 7, 11, 12):
                    warn(filename, lineno, f"'{field}' valor atípico: {val}")
            except ValueError:
                err(filename, lineno, f"'{field}' não é inteiro: {val}")

        elif ftype == "enum":
            if "values" in rules and val not in rules["values"]:
                err(filename, lineno, f"'{field}' valor inválido '{val}', esperado {rules['values']}")

        elif ftype == "non_neg_int":
            try:
                iv = int(val)
                if iv < 0:
                    err(filename, lineno, f"'{field}' não pode ser negativo: {val}")
            except ValueError:
                err(filename, lineno, f"'{field}' não é inteiro: {val}")

        elif ftype == "non_neg_float":
            try:
                fv = float(val)
                if fv < 0:
                    err(filename, lineno, f"'{field}' não pode ser negativo: {val}")
            except ValueError:
                err(filename, lineno, f"'{field}' não é número: {val}")

        elif ftype == "timezone":
            if not val:
                pass
            elif val not in _COMMON_TIMEZONES:
                warn(filename, lineno, f"'{field}' fuso horário incomum: {val}")

        elif ftype == "lang":
            if not re.match(r"^[a-z]{2}(-[A-Z]{2})?$", val):
                warn(filename, lineno, f"'{field}' código de idioma incomum: {val}")

        elif ftype == "phone":
            pass

        elif ftype == "email":
            if "@" not in val:
                err(filename, lineno, f"'{field}' não parece email: {val}")

    # Check route must have short_name or long_name
    if filename == "routes.txt":
        has_short = row.get("route_short_name", "").strip()
        has_long = row.get("route_long_name", "").strip()
        if not has_short and not has_long:
            err(filename, lineno, "route_short_name e route_long_name ambos vazios (ao menos um é obrigatório)")


def validate_referential_integrity(all_data):
    service_ids = set()
    route_ids = set()
    trip_ids = set()
    stop_ids = set()
    shape_ids = set()
    agency_ids = set()

    if all_data["agency.txt"]:
        for r in all_data["agency.txt"]:
            agency_ids.add(r["agency_id"])
    if all_data["routes.txt"]:
        for r in all_data["routes.txt"]:
            route_ids.add(r["route_id"])
            if r.get("agency_id") and r["agency_id"] not in agency_ids:
                err("routes.txt", 0, f"agency_id '{r['agency_id']}' não encontrado em agency.txt")
    if all_data["calendar.txt"]:
        for r in all_data["calendar.txt"]:
            service_ids.add(r["service_id"])
    if all_data["calendar_dates.txt"]:
        for r in all_data["calendar_dates.txt"]:
            service_ids.add(r["service_id"])
    if all_data["stops.txt"]:
        for r in all_data["stops.txt"]:
            stop_ids.add(r["stop_id"])
    if all_data["trips.txt"]:
        for r in all_data["trips.txt"]:
            trip_ids.add(r["trip_id"])
            if r["route_id"] not in route_ids:
                err("trips.txt", 0, f"route_id '{r['route_id']}' não encontrado em routes.txt")
            if r["service_id"] not in service_ids:
                err("trips.txt", 0, f"service_id '{r['service_id']}' não encontrado em calendar.txt ou calendar_dates.txt")
            if r.get("shape_id") and r["shape_id"] not in shape_ids:
                shape_ids.add(r["shape_id"])
    if all_data["stop_times.txt"]:
        for r in all_data["stop_times.txt"]:
            if r["trip_id"] not in trip_ids:
                err("stop_times.txt", 0, f"trip_id '{r['trip_id']}' não encontrado em trips.txt")
            if r["stop_id"] not in stop_ids:
                err("stop_times.txt", 0, f"stop_id '{r['stop_id']}' não encontrado em stops.txt")
    if all_data["shapes.txt"]:
        known = set()
        for r in all_data["shapes.txt"]:
            known.add(r["shape_id"])
        shape_ids_from_trips = {r["shape_id"] for r in (all_data["trips.txt"] or []) if r.get("shape_id")}
        missing = shape_ids_from_trips - known
        for sid in missing:
            err("shapes.txt", 0, f"shape_id '{sid}' referenciado em trips.txt mas não encontrado em shapes.txt")

    if all_data["transfers.txt"]:
        for r in all_data["transfers.txt"]:
            if r["from_stop_id"] not in stop_ids:
                err("transfers.txt", 0, f"from_stop_id '{r['from_stop_id']}' não encontrado em stops.txt")
            if r["to_stop_id"] not in stop_ids:
                err("transfers.txt", 0, f"to_stop_id '{r['to_stop_id']}' não encontrado em stops.txt")


def validate_unique(filename, rows, keys):
    seen = set()
    for i, row in enumerate(rows):
        combo = tuple(row.get(k, "") for k in keys)
        if combo in seen:
            err(filename, i + 2, f"Chave duplicada ({', '.join(keys)}): {combo}")
        seen.add(combo)


def validate_sort_order(filename, rows, keys):
    prev_trip = None
    prev_seq = -1
    for i, row in enumerate(rows):
        trip = row.get(keys[0], "")
        try:
            seq = int(row.get(keys[1], -1))
        except ValueError:
            seq = -1
        if trip == prev_trip and seq < prev_seq:
            err(filename, i + 2, f"stop_sequence fora de ordem para trip_id '{trip}': {seq} após {prev_seq}")
        prev_trip = trip
        prev_seq = seq


def validate_times_consistency(filename, rows):
    for i, row in enumerate(rows):
        arr = row.get("arrival_time", "")
        dep = row.get("departure_time", "")
        if arr and dep:
            if dep < arr:
                warn(filename, i + 2, f"departure_time ({dep}) anterior a arrival_time ({arr})")


_COMMON_TIMEZONES = {
    "Africa/Abidjan", "Africa/Accra", "Africa/Addis_Ababa", "Africa/Algiers",
    "Africa/Asmara", "Africa/Bamako", "Africa/Bangui", "Africa/Banjul",
    "Africa/Bissau", "Africa/Blantyre", "Africa/Brazzaville", "Africa/Bujumbura",
    "Africa/Cairo", "Africa/Casablanca", "Africa/Ceuta", "Africa/Conakry",
    "Africa/Dakar", "Africa/Dar_es_Salaam", "Africa/Djibouti", "Africa/Douala",
    "Africa/El_Aaiun", "Africa/Freetown", "Africa/Gaborone", "Africa/Harare",
    "Africa/Johannesburg", "Africa/Juba", "Africa/Kampala", "Africa/Khartoum",
    "Africa/Kigali", "Africa/Kinshasa", "Africa/Lagos", "Africa/Libreville",
    "Africa/Lome", "Africa/Luanda", "Africa/Lubumbashi", "Africa/Lusaka",
    "Africa/Malabo", "Africa/Maputo", "Africa/Maseru", "Africa/Mbabane",
    "Africa/Mogadishu", "Africa/Monrovia", "Africa/Nairobi", "Africa/Ndjamena",
    "Africa/Niamey", "Africa/Nouakchott", "Africa/Ouagadougou", "Africa/Porto-Novo",
    "Africa/Sao_Tome", "Africa/Tripoli", "Africa/Tunis", "Africa/Windhoek",
    "America/Adak", "America/Anchorage", "America/Anguilla", "America/Antigua",
    "America/Araguaina", "America/Argentina/Buenos_Aires", "America/Argentina/Catamarca",
    "America/Argentina/Cordoba", "America/Argentina/Jujuy", "America/Argentina/La_Rioja",
    "America/Argentina/Mendoza", "America/Argentina/Rio_Gallegos", "America/Argentina/Salta",
    "America/Argentina/San_Juan", "America/Argentina/San_Luis", "America/Argentina/Tucuman",
    "America/Argentina/Ushuaia", "America/Aruba", "America/Asuncion", "America/Atikokan",
    "America/Bahia", "America/Bahia_Banderas", "America/Barbados", "America/Belem",
    "America/Belize", "America/Blanc-Sablon", "America/Boa_Vista", "America/Bogota",
    "America/Boise", "America/Cambridge_Bay", "America/Campo_Grande", "America/Cancun",
    "America/Caracas", "America/Cayenne", "America/Cayman", "America/Chicago",
    "America/Chihuahua", "America/Costa_Rica", "America/Creston", "America/Cuiaba",
    "America/Curacao", "America/Danmarkshavn", "America/Dawson", "America/Dawson_Creek",
    "America/Denver", "America/Detroit", "America/Dominica", "America/Edmonton",
    "America/Eirunepe", "America/El_Salvador", "America/Fort_Nelson", "America/Fortaleza",
    "America/Glace_Bay", "America/Goose_Bay", "America/Grand_Turk", "America/Grenada",
    "America/Guadeloupe", "America/Guatemala", "America/Guayaquil", "America/Guyana",
    "America/Halifax", "America/Havana", "America/Hermosillo", "America/Indiana/Indianapolis",
    "America/Indiana/Knox", "America/Indiana/Marengo", "America/Indiana/Petersburg",
    "America/Indiana/Tell_City", "America/Indiana/Vevay", "America/Indiana/Vincennes",
    "America/Indiana/Winamac", "America/Inuvik", "America/Iqaluit", "America/Jamaica",
    "America/Juneau", "America/Kentucky/Louisville", "America/Kentucky/Monticello",
    "America/Kralendijk", "America/La_Paz", "America/Lima", "America/Los_Angeles",
    "America/Lower_Princes", "America/Maceio", "America/Managua", "America/Manaus",
    "America/Marigot", "America/Martinique", "America/Matamoros", "America/Mazatlan",
    "America/Menominee", "America/Merida", "America/Metlakatla", "America/Mexico_City",
    "America/Miquelon", "America/Moncton", "America/Monterrey", "America/Montevideo",
    "America/Montserrat", "America/Nassau", "America/New_York", "America/Nipigon",
    "America/Nome", "America/Noronha", "America/North_Dakota/Beulah",
    "America/North_Dakota/Center", "America/North_Dakota/New_Salem", "America/Nuuk",
    "America/Ojinaga", "America/Panama", "America/Pangnirtung", "America/Paramaribo",
    "America/Phoenix", "America/Port-au-Prince", "America/Port_of_Spain",
    "America/Porto_Velho", "America/Puerto_Rico", "America/Punta_Arenas",
    "America/Rainy_River", "America/Rankin_Inlet", "America/Recife", "America/Regina",
    "America/Resolute", "America/Rio_Branco", "America/Santarem", "America/Santiago",
    "America/Santo_Domingo", "America/Sao_Paulo", "America/Scoresbysund",
    "America/Sitka", "America/St_Barthelemy", "America/St_Johns", "America/St_Kitts",
    "America/St_Lucia", "America/St_Thomas", "America/St_Vincent", "America/Swift_Current",
    "America/Tegucigalpa", "America/Thule", "America/Thunder_Bay", "America/Tijuana",
    "America/Toronto", "America/Tortola", "America/Vancouver", "America/Whitehorse",
    "America/Winnipeg", "America/Yakutat", "America/Yellowknife",
    "Antarctica/Casey", "Antarctica/Davis", "Antarctica/DumontDUrville",
    "Antarctica/Macquarie", "Antarctica/Mawson", "Antarctica/McMurdo",
    "Antarctica/Palmer", "Antarctica/Rothera", "Antarctica/Syowa", "Antarctica/Troll",
    "Antarctica/Vostok", "Arctic/Longyearbyen", "Asia/Aden", "Asia/Almaty",
    "Asia/Amman", "Asia/Anadyr", "Asia/Aqtau", "Asia/Aqtobe", "Asia/Ashgabat",
    "Asia/Atyrau", "Asia/Baghdad", "Asia/Bahrain", "Asia/Baku", "Asia/Bangkok",
    "Asia/Barnaul", "Asia/Beirut", "Asia/Bishkek", "Asia/Brunei", "Asia/Chita",
    "Asia/Choibalsan", "Asia/Colombo", "Asia/Damascus", "Asia/Dhaka", "Asia/Dili",
    "Asia/Dubai", "Asia/Dushanbe", "Asia/Famagusta", "Asia/Gaza", "Asia/Hebron",
    "Asia/Ho_Chi_Minh", "Asia/Hong_Kong", "Asia/Hovd", "Asia/Irkutsk",
    "Asia/Jakarta", "Asia/Jayapura", "Asia/Jerusalem", "Asia/Kabul", "Asia/Kamchatka",
    "Asia/Karachi", "Asia/Kathmandu", "Asia/Khandyga", "Asia/Kolkata", "Asia/Krasnoyarsk",
    "Asia/Kuala_Lumpur", "Asia/Kuching", "Asia/Kuwait", "Asia/Macau", "Asia/Magadan",
    "Asia/Makassar", "Asia/Manila", "Asia/Muscat", "Asia/Nicosia", "Asia/Novokuznetsk",
    "Asia/Novosibirsk", "Asia/Omsk", "Asia/Oral", "Asia/Phnom_Penh", "Asia/Pontianak",
    "Asia/Pyongyang", "Asia/Qatar", "Asia/Qostanay", "Asia/Qyzylorda",
    "Asia/Riyadh", "Asia/Sakhalin", "Asia/Samarkand", "Asia/Seoul", "Asia/Shanghai",
    "Asia/Singapore", "Asia/Srednekolymsk", "Asia/Taipei", "Asia/Tashkent",
    "Asia/Tbilisi", "Asia/Tehran", "Asia/Thimphu", "Asia/Tokyo", "Asia/Tomsk",
    "Asia/Ulaanbaatar", "Asia/Urumqi", "Asia/Ust-Nera", "Asia/Vientiane",
    "Asia/Vladivostok", "Asia/Yakutsk", "Asia/Yangon", "Asia/Yekaterinburg",
    "Asia/Yerevan", "Atlantic/Azores", "Atlantic/Bermuda", "Atlantic/Canary",
    "Atlantic/Cape_Verde", "Atlantic/Faroe", "Atlantic/Madeira", "Atlantic/Reykjavik",
    "Atlantic/South_Georgia", "Atlantic/St_Helena", "Atlantic/Stanley",
    "Australia/Adelaide", "Australia/Brisbane", "Australia/Broken_Hill",
    "Australia/Darwin", "Australia/Eucla", "Australia/Hobart", "Australia/Lindeman",
    "Australia/Lord_Howe", "Australia/Melbourne", "Australia/Perth", "Australia/Sydney",
    "Europe/Amsterdam", "Europe/Andorra", "Europe/Astrakhan", "Europe/Athens",
    "Europe/Belgrade", "Europe/Berlin", "Europe/Bratislava", "Europe/Brussels",
    "Europe/Bucharest", "Europe/Budapest", "Europe/Busingen", "Europe/Chisinau",
    "Europe/Copenhagen", "Europe/Dublin", "Europe/Gibraltar", "Europe/Guernsey",
    "Europe/Helsinki", "Europe/Isle_of_Man", "Europe/Istanbul", "Europe/Jersey",
    "Europe/Kaliningrad", "Europe/Kiev", "Europe/Kirov", "Europe/Lisbon",
    "Europe/Ljubljana", "Europe/London", "Europe/Luxembourg", "Europe/Madrid",
    "Europe/Malta", "Europe/Mariehamn", "Europe/Minsk", "Europe/Monaco",
    "Europe/Moscow", "Europe/Oslo", "Europe/Paris", "Europe/Podgorica",
    "Europe/Prague", "Europe/Riga", "Europe/Rome", "Europe/Samara", "Europe/San_Marino",
    "Europe/Sarajevo", "Europe/Saratov", "Europe/Simferopol", "Europe/Skopje",
    "Europe/Sofia", "Europe/Stockholm", "Europe/Tallinn", "Europe/Tirane",
    "Europe/Ulyanovsk", "Europe/Uzhgorod", "Europe/Vaduz", "Europe/Vatican",
    "Europe/Vienna", "Europe/Vilnius", "Europe/Volgograd", "Europe/Warsaw",
    "Europe/Zagreb", "Europe/Zaporozhye", "Europe/Zurich",
    "Indian/Antananarivo", "Indian/Chagos", "Indian/Christmas", "Indian/Cocos",
    "Indian/Comoro", "Indian/Kerguelen", "Indian/Mahe", "Indian/Maldives",
    "Indian/Mauritius", "Indian/Mayotte", "Indian/Reunion",
    "Pacific/Apia", "Pacific/Auckland", "Pacific/Bougainville", "Pacific/Chatham",
    "Pacific/Chuuk", "Pacific/Easter", "Pacific/Efate", "Pacific/Enderbury",
    "Pacific/Fakaofo", "Pacific/Fiji", "Pacific/Funafuti", "Pacific/Galapagos",
    "Pacific/Gambier", "Pacific/Guadalcanal", "Pacific/Guam", "Pacific/Honolulu",
    "Pacific/Kiritimati", "Pacific/Kosrae", "Pacific/Kwajalein", "Pacific/Majuro",
    "Pacific/Marquesas", "Pacific/Midway", "Pacific/Nauru", "Pacific/Niue",
    "Pacific/Norfolk", "Pacific/Noumea", "Pacific/Pago_Pago", "Pacific/Palau",
    "Pacific/Pitcairn", "Pacific/Pohnpei", "Pacific/Port_Moresby", "Pacific/Rarotonga",
    "Pacific/Saipan", "Pacific/Tahiti", "Pacific/Tarawa", "Pacific/Tongatapu",
    "Pacific/Wake", "Pacific/Wallis",
}


def main():
    print("=" * 60)
    print("VALIDADOR GTFS - ESPECIFICAÇÃO OFICIAL")
    print("=" * 60)

    all_data = {}

    for fname in REQUIRED_FILES:
        exists = validate_file_exists(fname)
        if not exists:
            err(fname, 0, "Arquivo obrigatório ausente")

    # Read all files
    for fname in list(FILE_SPECS.keys()):
        rows, fields = read_csv(fname)
        all_data[fname] = rows

    # Validate each file
    for fname, spec in FILE_SPECS.items():
        rows = all_data[fname]
        if rows is None:
            if spec["required"]:
                err(fname, 0, "Arquivo obrigatório ausente")
            continue
        if len(rows) == 0:
            if spec["required"]:
                err(fname, 1, "Arquivo obrigatório sem dados (apenas cabeçalho)")
            else:
                warn(fname, 1, "Arquivo sem dados (apenas cabeçalho)")
            continue

        # Detect BOM
        path = os.path.join(GTFS_DIR, fname)
        with open(path, "rb") as f:
            raw = f.read(3)
            if raw == b"\xef\xbb\xbf":
                warn(fname, 0, "Arquivo contém BOM UTF-8 (geralmente aceito, mas incomum)")

        rows, fieldnames = read_csv(fname)
        all_data[fname] = rows

        print(f"\n--- {fname} ({len(rows)} registros) ---")
        validate_columns(fname, rows, fieldnames, spec)

        for i, row in enumerate(rows):
            validate_row(fname, row, i + 2, spec)

        if "unique" in spec:
            validate_unique(fname, rows, spec["unique"])

        if "sort_by" in spec:
            validate_sort_order(fname, rows, spec["sort_by"])

        if fname == "stop_times.txt":
            validate_times_consistency(fname, rows)

    print("\n--- INTEGRIDADE REFERENCIAL ---")
    validate_referential_integrity(all_data)

    # Summary
    print("\n" + "=" * 60)
    print("RESUMO DA VALIDAÇÃO")
    print("=" * 60)

    # Check if shapes.txt is needed
    if all_data["trips.txt"]:
        has_shape_ref = any(r.get("shape_id", "").strip() for r in all_data["trips.txt"])
        if has_shape_ref and all_data["shapes.txt"] is None:
            warn("(global)", 0, "trips.txt referencia shape_ids mas shapes.txt não existe")

    if errors:
        print(f"\nERROS: {len(errors)}")
        for e in errors:
            print(f"  [ERROR] {e}")
    else:
        print("\n[OK] Nenhum erro encontrado!")

    if warnings:
        print(f"\nAVISOS: {len(warnings)}")
        for w in warnings:
            print(f"  [WARN] {w}")
    else:
        print("[OK] Nenhum aviso.")

    print(f"\nTotal: {len(errors)} erros, {len(warnings)} avisos")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
