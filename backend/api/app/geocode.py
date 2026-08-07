import re

import httpx

from .models import Coordinates

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Suite/unit designators ("#47", "STE 47", "SUITE 47", "UNIT 3B", "APT 2")
# routinely trip up Nominatim even though they're irrelevant to locating the
# building itself -- strip them and retry before giving up.
_UNIT_RE = re.compile(r"[,]?\s*(?:#\s*\w+|\b(?:suite|ste|unit|apt)\.?\s*\w+)", re.IGNORECASE)


def geocode_address(address: str) -> Coordinates | None:
    for query in _query_variants(address):
        coordinates = _search(query)
        if coordinates is not None:
            return coordinates
    return None


def _query_variants(address: str) -> list[str]:
    variants = [address, _UNIT_RE.sub("", address)]
    seen: set[str] = set()
    cleaned = []
    for variant in variants:
        variant = re.sub(r"\s+", " ", variant).strip(" ,")
        if variant and variant not in seen:
            seen.add(variant)
            cleaned.append(variant)
    return cleaned


def _search(query: str) -> Coordinates | None:
    try:
        response = httpx.get(
            _NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
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
