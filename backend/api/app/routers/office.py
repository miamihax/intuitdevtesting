from fastapi import APIRouter, HTTPException

from ..data import DRIVERS, save_drivers
from ..geocode import geocode_address
from ..models import OfficeLocation, SetOfficeRequest
from ..office import get_office, set_office

router = APIRouter(prefix="/api/office")


@router.get("", response_model=OfficeLocation)
def read_office() -> OfficeLocation:
    return get_office()


@router.put("", response_model=OfficeLocation)
def update_office(request: SetOfficeRequest) -> OfficeLocation:
    geocode_result = geocode_address(request.address)
    if geocode_result is None:
        raise HTTPException(status_code=422, detail="Could not locate that address — check it and try again")

    office = set_office(request.address, geocode_result.coordinates)

    # Every driver starts/ends at the office — keep them all in sync so the
    # optimizer (which reads driver.depot directly) picks it up immediately.
    for driver in DRIVERS:
        driver.depot = geocode_result.coordinates
    save_drivers()

    return office
