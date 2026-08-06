import math

from .models import Coordinates


def haversine_km(a: Coordinates, b: Coordinates) -> float:
    radius_km = 6371.0
    lat1, lng1, lat2, lng2 = map(math.radians, [a.lat, a.lng, b.lat, b.lng])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(h))
