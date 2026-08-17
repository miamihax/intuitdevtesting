import httpx

from .geo import haversine_km
from .models import Coordinates, Store

# OSRM's free public demo server — no API key required. It gives real
# road-network driving times, but has NO live traffic: durations reflect
# typical road speeds, not current conditions, and the server is
# rate-limited / not meant for production use. For live-traffic-aware ETAs,
# swap this module's HTTP call for a paid provider (Google Maps Directions
# API, Mapbox Directions API) — the RouteMetrics shape below can stay the same.
OSRM_BASE_URL = "https://router.project-osrm.org"
REQUEST_TIMEOUT_SECONDS = 8.0

# Assumed average city driving speed, used only if OSRM is unreachable.
FALLBACK_SPEED_KMH = 30.0


class RouteMetrics:
    def __init__(
        self,
        leg_durations_min: list[float],
        leg_distances_km: list[float],
        geometry: list[list[float]] | None,
        estimate_source: str,
    ):
        self.leg_durations_min = leg_durations_min
        self.leg_distances_km = leg_distances_km
        self.geometry = geometry
        self.estimate_source = estimate_source  # "road_network" | "straight_line_estimate"


def _fallback_metrics(depot: Coordinates, ordered_stops: list[Store]) -> RouteMetrics:
    durations: list[float] = []
    distances: list[float] = []
    current = depot
    for store in ordered_stops:
        dist_km = haversine_km(current, store.coordinates)
        distances.append(dist_km)
        durations.append((dist_km / FALLBACK_SPEED_KMH) * 60.0)
        current = store.coordinates
    return RouteMetrics(durations, distances, None, "straight_line_estimate")


def _haversine_matrix(points: list[Coordinates]) -> list[list[float]]:
    return [[haversine_km(a, b) for b in points] for a in points]


def get_duration_distance_matrix(
    depot: Coordinates, stores: list[Store]
) -> tuple[list[list[float]], list[list[float]], str]:
    """All-pairs driving duration (minutes) and distance (km) between the
    depot (matrix index 0) and each store (index i+1 for stores[i]), via
    OSRM's table service.

    Used by the optimizer to construct and refine a stop order against real
    road-network costs -- rather than straight-line distance -- without
    issuing a separate /route request per candidate ordering. Falls back to
    a haversine-based matrix (same assumed speed as get_route_metrics' local
    fallback) if OSRM is unreachable.
    """
    points = [depot] + [s.coordinates for s in stores]
    if len(points) <= 1:
        return [[0.0]], [[0.0]], "road_network"

    coords_str = ";".join(f"{c.lng},{c.lat}" for c in points)
    url = f"{OSRM_BASE_URL}/table/v1/driving/{coords_str}"

    try:
        response = httpx.get(
            url,
            params={"annotations": "duration,distance"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") != "Ok" or not data.get("durations"):
            raise ValueError(f"OSRM table returned no usable matrix: {data.get('code')}")

        duration_min = [[d / 60.0 for d in row] for row in data["durations"]]
        distances_m = data.get("distances")
        if distances_m is not None:
            distance_km = [[d / 1000.0 for d in row] for row in distances_m]
        else:
            distance_km = _haversine_matrix(points)
        return duration_min, distance_km, "road_network"
    except Exception:
        # Network failure, timeout, rate limit, or malformed response --
        # degrade to a straight-line/assumed-speed matrix rather than
        # failing the request.
        distance_km = _haversine_matrix(points)
        duration_min = [[(d / FALLBACK_SPEED_KMH) * 60.0 for d in row] for row in distance_km]
        return duration_min, distance_km, "straight_line_estimate"


def get_route_metrics(depot: Coordinates, ordered_stops: list[Store]) -> RouteMetrics:
    """Get driving duration/distance per leg and a road-snapped geometry for
    depot -> stop1 -> stop2 -> ... -> stopN, in that fixed order.

    This does NOT re-order stops (that's the optimizer's job) — it only
    measures the route the optimizer already chose. Falls back to a
    straight-line/assumed-speed estimate if OSRM is unreachable or errors.
    """
    if not ordered_stops:
        return RouteMetrics([], [], None, "road_network")

    waypoints = [depot] + [s.coordinates for s in ordered_stops]
    coords_str = ";".join(f"{c.lng},{c.lat}" for c in waypoints)
    url = f"{OSRM_BASE_URL}/route/v1/driving/{coords_str}"

    try:
        response = httpx.get(
            url,
            params={"overview": "full", "geometries": "geojson", "annotations": "duration,distance"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM returned no usable route: {data.get('code')}")

        route = data["routes"][0]
        leg_durations_min = [leg["duration"] / 60.0 for leg in route["legs"]]
        leg_distances_km = [leg["distance"] / 1000.0 for leg in route["legs"]]
        geometry = route.get("geometry", {}).get("coordinates")
        return RouteMetrics(leg_durations_min, leg_distances_km, geometry, "road_network")
    except Exception:
        # Network failure, timeout, rate limit, or malformed response —
        # degrade to a straight-line estimate rather than failing the request.
        return _fallback_metrics(depot, ordered_stops)
