import re
from dataclasses import dataclass

import httpx

from .models import Coordinates

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Suite/unit designators ("#47", "STE 47", "SUITE 47", "UNIT 3B", "APT 2")
# routinely trip up Nominatim even though they're irrelevant to locating the
# building itself -- strip them and retry before giving up.
_UNIT_RE = re.compile(r"[,]?\s*(?:#\s*\w+|\b(?:suite|ste|unit|apt)\.?\s*\w+)", re.IGNORECASE)
# The state + ZIP at the tail of a US address -- used as a last-resort
# fallback query when Nominatim has no data for the exact address at all
# (a real coverage gap, not a formatting problem -- e.g. house numbers on
# rural highways are often unindexed). This only narrows down to the
# postal code's centroid, so a match via this path is flagged approximate.
_STATE_ZIP_RE = re.compile(r"\b([A-Z]{2})\s+(\d{5})(?:-\d{4})?\b")


@dataclass
class GeocodeResult:
    coordinates: Coordinates
    approximate: bool  # True when this came from the ZIP-centroid fallback, not the address itself


def geocode_address(address: str) -> GeocodeResult | None:
    for query in _query_variants(address):
        coordinates = _search(query)
        if coordinates is not None:
            return GeocodeResult(coordinates=coordinates, approximate=False)

    zip_query = _zip_centroid_query(address)
    if zip_query:
        coordinates = _search(zip_query)
        if coordinates is not None:
            return GeocodeResult(coordinates=coordinates, approximate=True)

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


def _zip_centroid_query(address: str) -> str | None:
    matches = list(_STATE_ZIP_RE.finditer(address))
    if not matches:
        return None
    state, zip_code = matches[-1].groups()
    return f"{zip_code}, {state}"


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
