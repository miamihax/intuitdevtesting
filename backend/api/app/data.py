import json
import threading

from .blob_store import load_json, save_json, using_blob
from .models import Driver, Store
from .paths import DATA_DIR

# Persisted so confirmed orders and drivers survive a backend restart or page
# refresh instead of resetting. On Vercel this goes to Blob storage rather
# than DATA_DIR -- see blob_store.py for why (the /tmp files DATA_DIR
# resolves to there don't survive a cold start, causing "Unknown store ids" /
# "Unknown driver id" the next time a request lands on a fresh instance).
_STORES_PATH = DATA_DIR / "stores.json"
_DRIVERS_PATH = DATA_DIR / "drivers.json"
_lock = threading.Lock()


def save_stores() -> None:
    with _lock:
        if using_blob():
            save_json("stores.json", [store.model_dump() for store in STORES])
            return
        _STORES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STORES_PATH.write_text(json.dumps([store.model_dump() for store in STORES]))


def _load_stores() -> list[Store]:
    if using_blob():
        raw = load_json("stores.json")
        return [Store.model_validate(s) for s in raw] if raw is not None else []
    if _STORES_PATH.exists():
        return [Store.model_validate(s) for s in json.loads(_STORES_PATH.read_text())]
    # No example orders — populated via "Import Orders" / "Edit Orders" once
    # real data exists.
    return []


STORES: list[Store] = _load_stores()


def save_drivers() -> None:
    with _lock:
        if using_blob():
            save_json("drivers.json", [driver.model_dump() for driver in DRIVERS])
            return
        _DRIVERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DRIVERS_PATH.write_text(json.dumps([driver.model_dump() for driver in DRIVERS]))


def _load_drivers() -> list[Driver]:
    if using_blob():
        raw = load_json("drivers.json")
        return [Driver.model_validate(d) for d in raw] if raw is not None else []
    if _DRIVERS_PATH.exists():
        return [Driver.model_validate(d) for d in json.loads(_DRIVERS_PATH.read_text())]
    # No example drivers — populated via "Edit Drivers" once real ones exist.
    return []


DRIVERS: list[Driver] = _load_drivers()
