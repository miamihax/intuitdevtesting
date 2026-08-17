import uuid

from .data import STORES, save_stores
from .models import Coordinates, Store

DEFAULT_TIME_WINDOW_START = "09:00"
DEFAULT_TIME_WINDOW_END = "19:00"


def unique_store_id(invoice_number: str | None) -> str:
    # Prefer the invoice number as the order ID so it's traceable back to
    # its source document -- fall back to a random ID when one wasn't
    # extracted. Since store IDs must be unique (used for lookups, edits,
    # and deletes), disambiguate a colliding invoice number (e.g. the same
    # invoice re-uploaded, or two distributors reusing the same number)
    # instead of silently overwriting an existing order with the same ID.
    base = invoice_number or f"import-{uuid.uuid4().hex[:8]}"
    existing_ids = {store.id for store in STORES}
    if base not in existing_ids:
        return base
    suffix = 2
    while f"{base}-{suffix}" in existing_ids:
        suffix += 1
    return f"{base}-{suffix}"


def add_store(
    *,
    invoice_number: str | None,
    name: str,
    address: str,
    coordinates: Coordinates,
    approximate_location: bool,
    time_window_start: str | None,
    time_window_end: str | None,
    case_count: int | None,
) -> Store:
    store = Store(
        id=unique_store_id(invoice_number),
        name=name,
        address=address,
        coordinates=coordinates,
        approximate_location=approximate_location,
        time_window_start=time_window_start or DEFAULT_TIME_WINDOW_START,
        time_window_end=time_window_end or DEFAULT_TIME_WINDOW_END,
        case_count=case_count or 0,
    )
    STORES.append(store)
    save_stores()
    return store
