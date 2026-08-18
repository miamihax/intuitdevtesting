import os
import re
from dataclasses import dataclass

import httpx

from .geo import haversine_km
from .models import Coordinates

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# OSM's own free, no-API-key query endpoint over the full tagged dataset --
# used as a second name-search pass when Nominatim's text search comes up
# empty. Overpass matches tags directly (e.g. name="Total Wine & More")
# rather than doing fuzzy free-text ranking, so it can find a place even
# when the address text uses different road-naming conventions than OSM
# does ("State Route 36" vs. "NJ-36") -- exactly the kind of mismatch that
# defeats a plain text search but not a tag match.
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
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
# A name-search match (see _name_query_variants) only counts as a real find
# if it's at least in the right area -- Nominatim ranks POI name matches by
# global relevance, not distance, so an ungrounded chain-store name search
# ("Total Wine & More", "CVS", ...) can just as easily return a same-named
# branch one town over as the right one (confirmed against a real chain
# name: a same-state, same-chain false match landed ~27km from the correct
# ZIP centroid -- well within a looser threshold, which is why this is
# tight). Reject anything farther from the ZIP centroid than this and fall
# back to the ZIP guess instead of trusting a confident-looking but wrong
# match. A ZIP code area itself is rarely more than ~10km across.
_NAME_MATCH_MAX_KM = 12.0

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
# Best-effort US street address matcher for pulling a real address out of a
# Brave search result's title/description text (e.g. "123 Main St, Anytown,
# NJ 07001 · Hours · (555) 555-0100"). Requires exactly the
# "street, city, ST ZIP" shape -- strict enough to avoid grabbing unrelated
# digit runs (phone numbers, hours) out of the surrounding text.
_STREET_ADDRESS_RE = re.compile(
    r"\b(\d{1,6}\s+[^,\n]{3,60}),\s*([A-Za-z .'-]{2,40}),\s*([A-Z]{2})\s+(\d{5})(?:-\d{4})?\b"
)
# Business-listing sites spell out highway addresses in whatever house style
# they use ("66 NJ Rte 36", "66 State Route 36") -- Nominatim's parser
# frequently only recognizes OSM's own hyphenated state-route form ("66
# NJ-36"). Rewrite one into the other when a route number is present.
_ROUTE_ABBREV_RE = re.compile(r"\b(?:rte|route|hwy|highway)\.?\s*(\d+[a-z]?)\b", re.IGNORECASE)


@dataclass
class GeocodeResult:
    coordinates: Coordinates
    approximate: bool  # True when this came from the ZIP-centroid fallback, not the address itself
    # Set only when a name search (not the address itself) is what actually
    # matched -- the real address behind the coordinates, which can differ
    # from whatever address text was given. Callers should prefer this over
    # their own address string when it's present, so the displayed address
    # always reflects the place the coordinates actually point at.
    resolved_address: str | None = None


@dataclass
class _SearchHit:
    coordinates: Coordinates
    display_name: str


def geocode_address(address: str, name: str | None = None, use_web_fallback: bool = True) -> GeocodeResult | None:
    for query in _query_variants(address):
        hit = _search(query)
        if hit is not None:
            return GeocodeResult(coordinates=hit.coordinates, approximate=False)

    zip_query = _zip_centroid_query(address)
    zip_hit = _search(zip_query) if zip_query else None

    # The street address alone didn't resolve (bad house number, OCR typo,
    # an unindexed rural road, ...) -- if we know the business/location
    # name, try searching for that instead. Nominatim indexes named places
    # (POIs) in addition to street addresses, so a chain store or landmark
    # often resolves this way even when its raw address doesn't. Only
    # accept it if it lands near the ZIP the address itself claims --
    # otherwise it's more likely a same-named place somewhere else entirely.
    if name:
        for query in _name_query_variants(name, address):
            hit = _search(query)
            if hit is None:
                continue
            if zip_hit is None or haversine_km(hit.coordinates, zip_hit.coordinates) <= _NAME_MATCH_MAX_KM:
                return GeocodeResult(
                    coordinates=hit.coordinates,
                    approximate=False,
                    resolved_address=_clean_display_name(hit.display_name),
                )

        # Nominatim's own name index came up empty (or only found an
        # ungrounded same-named place elsewhere) -- Overpass queries OSM's
        # tags directly and can succeed where Nominatim's text search
        # didn't. Radius-constrained around the ZIP centroid from the
        # start, so (unlike the Nominatim pass above) there's no separate
        # distance check needed -- it can't return something far away.
        if zip_hit is not None:
            overpass_hit = _overpass_name_search(name, zip_hit.coordinates)
            if overpass_hit is not None:
                return GeocodeResult(
                    coordinates=overpass_hit.coordinates,
                    approximate=False,
                    resolved_address=overpass_hit.display_name or None,
                )

        # OSM has no data on this place at all -- last resort, ask a general
        # web search for the place and pull a street address out of the
        # results, then geocode that. Only runs when BRAVE_SEARCH_API_KEY is
        # set (Brave's free tier); silently skipped otherwise.
        if use_web_fallback:
            web_result = suggest_address_via_web(address, name, zip_hit=zip_hit)
            if web_result is not None:
                return web_result

    if zip_hit is not None:
        return GeocodeResult(coordinates=zip_hit.coordinates, approximate=True)

    return None


def suggest_address_via_web(
    address: str, name: str, zip_hit: "_SearchHit | None" = None
) -> GeocodeResult | None:
    """Same web-search-and-geocode step `geocode_address` folds in as its
    last resort, but exposed on its own. Intended for callers (the import
    review flow) that want to surface this as a suggestion for a human to
    accept rather than apply it automatically."""
    if zip_hit is None:
        zip_query = _zip_centroid_query(address)
        zip_hit = _search(zip_query) if zip_query else None

    candidates = _brave_search_addresses(name, address)
    for candidate in candidates:
        hit = _search(candidate)
        if hit is None:
            continue
        if zip_hit is None or haversine_km(hit.coordinates, zip_hit.coordinates) <= _NAME_MATCH_MAX_KM:
            return GeocodeResult(coordinates=hit.coordinates, approximate=False, resolved_address=candidate)

    # None of the candidates independently geocode -- OSM sometimes has no
    # address point at all for a given house number (rural highways, strip
    # malls with thin coverage), no matter how the street name is phrased.
    # Still surface the best candidate's address text as a suggestion: a
    # human reviewer can recognize it's correct even without a precise pin,
    # which beats showing nothing. Coordinates fall back to the ZIP centroid
    # (still flagged approximate) since that's the best guess available.
    if candidates and zip_hit is not None:
        return GeocodeResult(coordinates=zip_hit.coordinates, approximate=True, resolved_address=candidates[0])

    return None


def _clean_display_name(display_name: str) -> str | None:
    # Nominatim's display_name is a long, comma-separated hierarchy (down to
    # county and country) -- trim the trailing country for a more usable
    # address string, similar in shape to what OCR/QuickBooks produce.
    if not display_name:
        return None
    return re.sub(r",\s*United States( of America)?$", "", display_name).strip()


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


def _name_query_variants(name: str, address: str) -> list[str]:
    # Try the name alongside the full address first (most context -- can
    # still anchor to the right town/street even if the house number is
    # what's wrong), then fall back to just the name plus state/ZIP (looser,
    # for cases where the address text itself is confusing the search).
    variants = [f"{name}, {address}"]
    state_zip = _zip_centroid_query(address)
    if state_zip:
        variants.append(f"{name}, {state_zip}")

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


def _overpass_name_search(name: str, center: Coordinates, radius_km: float = _NAME_MATCH_MAX_KM) -> _SearchHit | None:
    # Restricted to elements tagged as a shop/amenity/office -- an
    # unrestricted name-tag search scans every named element in the radius
    # (streets, buildings, waterways, ...) and is slow enough to time out.
    # This app only ever geocodes delivery destinations (stores, bars,
    # restaurants, offices), so it's also a better semantic match, not just
    # a performance one.
    around = f"(around:{int(radius_km * 1000)},{center.lat},{center.lng})"
    name_filter = f'["name"~"{_overpass_regex_literal(name)}",i]'
    # The public Overpass instance is shared and often slow (observed
    # 20-45s+ under load, vs. Nominatim's typically sub-second responses) --
    # cap it well below that so a slow response degrades to the ZIP-centroid
    # fallback instead of leaving an order edit hanging for tens of seconds.
    query = (
        "[out:json][timeout:8];"
        "("
        f'nwr["shop"]{name_filter}{around};'
        f'nwr["amenity"]{name_filter}{around};'
        f'nwr["office"]{name_filter}{around};'
        ");"
        "out center 1;"
    )
    try:
        response = httpx.post(
            _OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": "OptiRoute/1.0 (delivery route planning demo)"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError:
        return None

    elements = data.get("elements") or []
    if not elements:
        return None

    element = elements[0]
    lat, lon = element.get("lat"), element.get("lon")
    if lat is None or lon is None:
        # Ways/relations (e.g. a mapped building footprint) don't have a
        # single point of their own -- "out center" computes one instead.
        center_point = element.get("center") or {}
        lat, lon = center_point.get("lat"), center_point.get("lon")
    if lat is None or lon is None:
        return None

    return _SearchHit(
        coordinates=Coordinates(lat=float(lat), lng=float(lon)),
        display_name=_address_from_osm_tags(element.get("tags") or {}),
    )


def _overpass_regex_literal(name: str) -> str:
    # Overpass's ["key"~"regex"] value is a regex, not a literal string --
    # escape it so a name containing regex-special characters (e.g. "&",
    # parens) is matched literally, then escape any quote so it can't break
    # out of the quoted query string.
    return re.escape(name).replace('"', '\\"')


def _address_from_osm_tags(tags: dict) -> str:
    house_and_street = " ".join(p for p in [tags.get("addr:housenumber"), tags.get("addr:street")] if p)
    state_and_zip = " ".join(p for p in [tags.get("addr:state"), tags.get("addr:postcode")] if p)
    city_line = ", ".join(p for p in [tags.get("addr:city"), state_and_zip] if p)
    parts = [p for p in [tags.get("name"), house_and_street, city_line] if p]
    return ", ".join(parts)


def _route_address_variant(street: str, state: str) -> str | None:
    route_match = _ROUTE_ABBREV_RE.search(street)
    housenumber_match = re.match(r"^(\d{1,6})\b", street)
    if not route_match or not housenumber_match:
        return None
    return f"{housenumber_match.group(1)} {state}-{route_match.group(1)}"


def _brave_search_addresses(name: str, address: str) -> list[str]:
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return []

    # Anchor the search to the ZIP/state the address claims when available --
    # a bare name search ("Total Wine & More") is too ambiguous otherwise.
    state_zip = _zip_centroid_query(address)
    query = f"{name} {state_zip}" if state_zip else f"{name} {address}"

    try:
        response = httpx.get(
            _BRAVE_SEARCH_URL,
            params={"q": query, "count": 5},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            timeout=6.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError:
        return []

    results = (data.get("web") or {}).get("results") or []
    candidates: list[str] = []
    seen: set[str] = set()
    for result in results:
        text = " ".join(filter(None, [result.get("title"), result.get("description")]))
        match = _STREET_ADDRESS_RE.search(text)
        if not match:
            continue
        street, city, state, zip_code = (g.strip() for g in match.groups())
        # Try the highway-normalized form first -- it's the one more likely
        # to match Nominatim's own address parsing.
        for street_form in filter(None, [_route_address_variant(street, state), street]):
            candidate = f"{street_form}, {city}, {state} {zip_code}"
            if candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)

    return candidates


def _search(query: str) -> _SearchHit | None:
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
    result = results[0]
    return _SearchHit(
        coordinates=Coordinates(lat=float(result["lat"]), lng=float(result["lon"])),
        display_name=result.get("display_name", ""),
    )
