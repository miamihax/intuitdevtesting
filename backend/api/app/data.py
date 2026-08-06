from .models import Driver, Store
from .office import DEFAULT_COORDINATES

# No example orders — populated via "Import Orders" / "Edit Orders" once
# real data exists. Add Store(...) entries here (or wire up a real data
# source) when you're ready to seed it again.
STORES: list[Store] = []

DRIVERS: list[Driver] = [
    Driver(
        id="d1",
        name="Marcus Reed",
        depot=DEFAULT_COORDINATES,
        vehicle_capacity_cases=60,
        shift_start="08:00",
        shift_end="16:00",
    ),
    Driver(
        id="d2",
        name="Elena Cho",
        depot=DEFAULT_COORDINATES,
        vehicle_capacity_cases=60,
        shift_start="08:00",
        shift_end="16:00",
    ),
]
