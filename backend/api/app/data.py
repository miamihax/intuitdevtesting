import json
import threading

from .models import Driver, Store
from .office import get_office
from .paths import DATA_DIR

# No example orders — populated via "Import Orders" / "Edit Orders" once
# real data exists. Add Store(...) entries here (or wire up a real data
# source) when you're ready to seed it again.
STORES: list[Store] = []

# Persisted the same way office.py persists its state, so drivers survive a
# backend restart or page refresh instead of resetting to the seed list.
_DRIVERS_PATH = DATA_DIR / "drivers.json"
_lock = threading.Lock()


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
