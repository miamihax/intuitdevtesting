import json
import threading

from .models import Driver, Store
from .paths import DATA_DIR

# Persisted the same way office.py persists its state, so confirmed orders
# and drivers survive a backend restart or page refresh instead of resetting
# (a Vercel cold start otherwise wipes them while the frontend still holds
# stale IDs in memory, causing "Unknown store ids" on the next optimize call).
_STORES_PATH = DATA_DIR / "stores.json"
_DRIVERS_PATH = DATA_DIR / "drivers.json"
_lock = threading.Lock()


def save_stores() -> None:
    with _lock:
        _STORES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STORES_PATH.write_text(json.dumps([store.model_dump() for store in STORES]))


if _STORES_PATH.exists():
    STORES: list[Store] = [Store.model_validate(s) for s in json.loads(_STORES_PATH.read_text())]
else:
    # No example orders — populated via "Import Orders" / "Edit Orders" once
    # real data exists.
    STORES = []


def save_drivers() -> None:
    with _lock:
        _DRIVERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DRIVERS_PATH.write_text(json.dumps([driver.model_dump() for driver in DRIVERS]))


if _DRIVERS_PATH.exists():
    DRIVERS: list[Driver] = [Driver.model_validate(d) for d in json.loads(_DRIVERS_PATH.read_text())]
else:
    # No example drivers — populated via "Edit Drivers" once real ones exist.
    DRIVERS = []
