import threading

from .models import Coordinates, OfficeLocation
from .paths import DATA_DIR

# Same coordinates data.py used to hardcode as the shared driver depot —
# kept here so both data.py (initial driver depots) and this module (the
# office-location state itself) point at one definition.
DEFAULT_ADDRESS = "824 Ridgewood Ave, North Brunswick, NJ 08902"
DEFAULT_COORDINATES = Coordinates(lat=40.4634826, lng=-74.4684451)

# Persisted to disk (not just kept in memory) so the office location survives
# a backend restart or page refresh — same DATA_DIR pattern as qbo_tokens.py.
_OFFICE_PATH = DATA_DIR / "office.json"
_lock = threading.Lock()


def _read() -> OfficeLocation:
    if _OFFICE_PATH.exists():
        return OfficeLocation.model_validate_json(_OFFICE_PATH.read_text())
    return OfficeLocation(address=DEFAULT_ADDRESS, coordinates=DEFAULT_COORDINATES)


def get_office() -> OfficeLocation:
    with _lock:
        return _read()


def set_office(address: str, coordinates: Coordinates) -> OfficeLocation:
    office = OfficeLocation(address=address, coordinates=coordinates)
    with _lock:
        _OFFICE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _OFFICE_PATH.write_text(office.model_dump_json())
    return office
