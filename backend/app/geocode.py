import httpx

from .models import Coordinates

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode_address(address: str) -> Coordinates | None:
    try:
        response = httpx.get(
            _NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "OptiRoute/1.0 (delivery route planning demo)"},
            timeout=5.0,
        )
        response.raise_for_status()
        results = response.json()
    except httpx.HTTPError:
        return None
    if not results:
        return None
    return Coordinates(lat=float(results[0]["lat"]), lng=float(results[0]["lon"]))
