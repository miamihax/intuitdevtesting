import json
import threading

from .models import Driver, Store
from .office import get_office
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


def _default_drivers() -> list[Driver]:
    # Read whatever office location was already persisted (see office.py)
    # rather than always the hardcoded default — otherwise a restart would
    # reset every driver's depot even though the saved office didn't change.
    depot = get_office().coordinates
    return [
        Driver(
            id="d1",
            name="Marcus Reed",
            depot=depot,
            vehicle_capacity_cases=60,
            shift_start="08:00",
            shift_end="16:00",
        ),
        Driver(
            id="d2",
            name="Elena Cho",
            depot=depot,
            vehicle_capacity_cases=60,
            shift_start="08:00",
            shift_end="16:00",
        ),
    ]


def save_drivers() -> None:
    with _lock:
        _DRIVERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DRIVERS_PATH.write_text(json.dumps([driver.model_dump() for driver in DRIVERS]))


if _DRIVERS_PATH.exists():
    DRIVERS: list[Driver] = [Driver.model_validate(d) for d in json.loads(_DRIVERS_PATH.read_text())]
else:
    DRIVERS = _default_drivers()
    save_drivers()
