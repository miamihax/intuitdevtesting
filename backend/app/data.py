from .models import Coordinates, Driver, Store

# No example orders — populated via "Import Orders" / "Edit Orders" once
# real data exists. Add Store(...) entries here (or wire up a real data
# source) when you're ready to seed it again.
STORES: list[Store] = []

# Shared distribution center depot for both drivers.
_DEPOT = Coordinates(lat=41.8850, lng=-87.6298)

DRIVERS: list[Driver] = [
    Driver(
        id="d1",
        name="Marcus Reed",
        depot=_DEPOT,
        vehicle_capacity_cases=60,
        shift_start="08:00",
        shift_end="16:00",
    ),
    Driver(
        id="d2",
        name="Elena Cho",
        depot=_DEPOT,
        vehicle_capacity_cases=60,
        shift_start="08:00",
        shift_end="16:00",
    ),
]
