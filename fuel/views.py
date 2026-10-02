import math
import threading
import time

import requests
from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import FuelStop

MPG = 10.0
MAX_RANGE_MILES = 500.0
NEAR_ROUTE_MILES = 25.0
STATES = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"}
_GEOCODE_LOCK = threading.Lock()
_GEOCODE_CACHE = {}
_LAST_GEOCODE_AT = 0.0


def _geocode(place):
    global _LAST_GEOCODE_AT
    key = place.casefold()
    with _GEOCODE_LOCK:
        if key in _GEOCODE_CACHE:
            return _GEOCODE_CACHE[key]
        delay = 1.0 - (time.monotonic() - _LAST_GEOCODE_AT)
        if delay > 0:
            time.sleep(delay)
        response = requests.get(settings.GEOCODER_URL, params={"q": place, "format": "jsonv2", "countrycodes": "us", "limit": 1}, headers={"User-Agent": settings.GEOCODER_USER_AGENT}, timeout=8)
        _LAST_GEOCODE_AT = time.monotonic()
        response.raise_for_status()
        results = response.json()
        if not results:
            raise ValueError(f"Could not find a US location for '{place}'. Include city and state.")
        result = (float(results[0]["lon"]), float(results[0]["lat"]), results[0].get("display_name", place))
        if len(_GEOCODE_CACHE) >= 1024:
            _GEOCODE_CACHE.pop(next(iter(_GEOCODE_CACHE)))
        _GEOCODE_CACHE[key] = result
        return result


def _haversine(a, b):
    lon1, lat1 = a
    lon2, lat2 = b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def _project_station(stop, line):
    """Return approximate route mile and distance-to-route using local segments."""
    best = (float("inf"), 0.0)
    walked = 0.0
    for a, b in zip(line, line[1:]):
        length = _haversine(a, b)
        lat_scale = 69.0
        lon_scale = 69.0 * math.cos(math.radians((a[1] + b[1]) / 2))
        vx, vy = (b[0] - a[0]) * lon_scale, (b[1] - a[1]) * lat_scale
        wx, wy = (stop.longitude - a[0]) * lon_scale, (stop.latitude - a[1]) * lat_scale
        denom = vx * vx + vy * vy
        t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom)) if denom else 0.0
        gap = math.hypot(wx - t * vx, wy - t * vy)
        if gap < best[0]:
            best = (gap, walked + t * length)
        walked += length
    return best[1], best[0]


def _fuel_plan(line, route_miles):
    mid_lat = sum(point[1] for point in line) / len(line)
    lat_pad = NEAR_ROUTE_MILES / 69.0
    lon_pad = min(180.0, NEAR_ROUTE_MILES / max(10.0, 69.0 * abs(math.cos(math.radians(mid_lat)))))
    stops = list(FuelStop.objects.filter(latitude__isnull=False, longitude__isnull=False)
                 .filter(latitude__gte=min(p[1] for p in line) - lat_pad, latitude__lte=max(p[1] for p in line) + lat_pad)
                 .filter(longitude__gte=min(p[0] for p in line) - lon_pad, longitude__lte=max(p[0] for p in line) + lon_pad)
                 .only("id", "name", "address", "city", "state", "price_per_gallon", "latitude", "longitude"))
    candidates = []
    for station in stops:
        mile, offroute = _project_station(station, line)
        if offroute <= NEAR_ROUTE_MILES and -1 <= mile <= route_miles + 1:
            candidates.append({"station": station, "mile": max(0.0, mile), "offroute": offroute})
    candidates.sort(key=lambda item: item["mile"])
    plan, position, total_cost = [], 0.0, 0.0
    while route_miles - position > MAX_RANGE_MILES:
        reachable = [item for item in candidates if position + 1 < item["mile"] <= position + MAX_RANGE_MILES]
        if not reachable:
            raise ValueError(f"No mapped fuel stop within {MAX_RANGE_MILES:.0f} miles of the route near mile {position:.0f}. Load mapped fuel data or choose another route.")
        next_stop = min(reachable, key=lambda item: (float(item["station"].price_per_gallon), -item["mile"]))
        leg_miles = next_stop["mile"] - position
        gallons = leg_miles / MPG
        cost = gallons * float(next_stop["station"].price_per_gallon)
        total_cost += cost
        station = next_stop["station"]
        plan.append({"route_mile": round(next_stop["mile"], 1), "location": f"{station.city}, {station.state}", "name": station.name, "address": station.address, "latitude": station.latitude, "longitude": station.longitude, "price_per_gallon": float(station.price_per_gallon), "gallons": round(gallons, 2), "estimated_cost_usd": round(cost, 2), "miles_off_route": round(next_stop["offroute"], 2)})
        position = next_stop["mile"]
    remaining = route_miles - position
    if remaining > 0:
        available = [item for item in candidates if item["mile"] >= position and item["mile"] <= position + MAX_RANGE_MILES]
        if not available:
            raise ValueError(f"No mapped fuel stop within range near route mile {position:.0f}.")
        last = min(available, key=lambda item: float(item["station"].price_per_gallon))
        cost = remaining / MPG * float(last["station"].price_per_gallon)
        total_cost += cost
        station = last["station"]
        plan.append({"route_mile": round(last["mile"], 1), "location": f"{station.city}, {station.state}", "name": station.name, "address": station.address, "latitude": station.latitude, "longitude": station.longitude, "price_per_gallon": float(station.price_per_gallon), "gallons": round(remaining / MPG, 2), "estimated_cost_usd": round(cost, 2), "miles_off_route": round(last["offroute"], 2)})
    return plan, total_cost


@require_GET
def route_api(request):
    start, finish = request.GET.get("start", "").strip(), request.GET.get("finish", "").strip()
    if not start or not finish:
        return JsonResponse({"error": "Both 'start' and 'finish' query parameters are required."}, status=400)
    if len(start) > 200 or len(finish) > 200:
        return JsonResponse({"error": "Locations must be 200 characters or fewer."}, status=400)
    for place in (start, finish):
        parts = [part.strip().upper() for part in place.split(",")]
        if len(parts) < 2 or not any(part in STATES for part in parts):
            return JsonResponse({"error": "Provide US locations with a state, for example 'Boston, MA'."}, status=400)
    try:
        origin = _geocode(start)
        destination = _geocode(finish)
        url = f"{settings.ROUTER_URL}/{origin[0]},{origin[1]};{destination[0]},{destination[1]}"
        response = requests.get(url, params={"overview": "full", "geometries": "geojson", "steps": "false"}, headers={"User-Agent": "FuelRouteAssessment/1.0"}, timeout=15)
        response.raise_for_status()
        route_data = response.json()
        if route_data.get("code") != "Ok" or not route_data.get("routes"):
            return JsonResponse({"error": "The routing provider could not find a drivable route."}, status=422)
        route = route_data["routes"][0]
        coords = route["geometry"]["coordinates"]
        plan, total_cost = _fuel_plan(coords, route["distance"] / 1609.344)
        return JsonResponse({"start": {"input": start, "resolved": origin[2], "coordinates": {"longitude": origin[0], "latitude": origin[1]}}, "finish": {"input": finish, "resolved": destination[2], "coordinates": {"longitude": destination[0], "latitude": destination[1]}}, "distance_miles": round(route["distance"] / 1609.344, 1), "duration_seconds": round(route["duration"]), "fuel_economy_mpg": MPG, "maximum_range_miles": MAX_RANGE_MILES, "fuel_cost_usd": round(total_cost, 2), "fuel_stops": plan, "route": {"type": "LineString", "coordinates": coords}, "map_attribution": "© OpenStreetMap contributors · Routing by OSRM"})
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except requests.Timeout:
        return JsonResponse({"error": "A location or routing provider timed out. Please retry."}, status=504)
    except requests.RequestException:
        return JsonResponse({"error": "A location or routing provider is temporarily unavailable."}, status=502)


def index(request):
    return render(request, "index.html")

