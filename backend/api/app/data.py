from .models import Driver, Store
from .office import get_office

# No example orders — populated via "Import Orders" / "Edit Orders" once
# real data exists. Add Store(...) entries here (or wire up a real data
# source) when you're ready to seed it again.
STORES: list[Store] = []

# Read whatever office location was already persisted (see office.py) rather
# than always the hardcoded default — otherwise a backend restart would reset
# every driver's depot even though the saved office location didn't change.
_initial_depot = get_office().coordinates

DRIVERS: list[Driver] = [
    Driver(
        id="d1",
        name="Marcus Reed",
        depot=_initial_depot,
        vehicle_capacity_cases=60,
        shift_start="08:00",
        shift_end="16:00",
    ),
    Driver(
        id="d2",
        name="Elena Cho",
        depot=_initial_depot,
        vehicle_capacity_cases=60,
        shift_start="08:00",
        shift_end="16:00",
    ),
]
