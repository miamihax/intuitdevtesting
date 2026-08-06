import threading

from .models import Coordinates, OfficeLocation

# Same coordinates data.py used to hardcode as the shared driver depot —
# kept here so both data.py (initial driver depots) and this module (the
# office-location state itself) point at one definition.
DEFAULT_COORDINATES = Coordinates(lat=41.8850, lng=-87.6298)

_lock = threading.Lock()
_office = OfficeLocation(address=None, coordinates=DEFAULT_COORDINATES)


def get_office() -> OfficeLocation:
    with _lock:
        return _office


def set_office(address: str, coordinates: Coordinates) -> OfficeLocation:
    global _office
    with _lock:
        _office = OfficeLocation(address=address, coordinates=coordinates)
        return _office
