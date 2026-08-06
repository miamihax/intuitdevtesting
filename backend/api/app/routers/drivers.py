import uuid

from fastapi import APIRouter, HTTPException

from ..data import DRIVERS
from ..models import Driver, UpdateDriverRequest
from ..office import get_office

router = APIRouter(prefix="/api/drivers")


def _find(driver_id: str) -> Driver:
    driver = next((d for d in DRIVERS if d.id == driver_id), None)
    if driver is None:
        raise HTTPException(status_code=404, detail="Unknown driver id")
    return driver


@router.post("", response_model=Driver)
def create_driver(request: UpdateDriverRequest) -> Driver:
    driver = Driver(
        id=f"driver-{uuid.uuid4().hex[:8]}",
        name=request.name,
        depot=get_office().coordinates,
        vehicle_capacity_cases=request.vehicle_capacity_cases,
        shift_start=request.shift_start,
        shift_end=request.shift_end,
    )
    DRIVERS.append(driver)
    return driver


@router.put("/{driver_id}", response_model=Driver)
def update_driver(driver_id: str, request: UpdateDriverRequest) -> Driver:
    # depot isn't editable per-driver — it's controlled centrally via the
    # Office Location feature (see routers/office.py), which keeps every
    # driver's depot in sync whenever the office moves.
    driver = _find(driver_id)
    driver.name = request.name
    driver.vehicle_capacity_cases = request.vehicle_capacity_cases
    driver.shift_start = request.shift_start
    driver.shift_end = request.shift_end
    return driver


@router.delete("/{driver_id}")
def delete_driver(driver_id: str) -> dict[str, bool]:
    driver = _find(driver_id)
    DRIVERS.remove(driver)
    return {"ok": True}
