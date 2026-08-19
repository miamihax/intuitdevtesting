from fastapi import APIRouter, HTTPException

from ..data import DRIVERS, STORES, save_stores
from ..geocode import geocode_address
from ..models import (
    Driver,
    DriverRoute,
    OptimizeRequest,
    OptimizeResponse,
    ReorderRouteRequest,
    ResequenceRouteRequest,
    Store,
    UpdateStoreRequest,
)
from ..optimizer import build_route_for_order, build_routes, order_for_strategy

router = APIRouter(prefix="/api")


@router.get("/stores", response_model=list[Store])
def list_stores() -> list[Store]:
    return STORES


@router.put("/stores/{store_id}", response_model=Store)
def update_store(store_id: str, request: UpdateStoreRequest) -> Store:
    store = next((s for s in STORES if s.id == store_id), None)
    if store is None:
        raise HTTPException(status_code=404, detail="Unknown store id")

    address = request.address
    coordinates = store.coordinates
    approximate_location = store.approximate_location

    # Only re-geocode when the address text actually changed -- editing the
    # name/time window/case count shouldn't cost a geocode call or touch
    # coordinates that are still correct.
    if request.address != store.address:
        geocode_result = geocode_address(request.address, request.name)
        if geocode_result is None:
            raise HTTPException(status_code=422, detail="Could not locate that address — check it and try again")
        coordinates = geocode_result.coordinates
        approximate_location = geocode_result.approximate
        # A name search can land on a different (correct) address than what
        # was typed -- prefer that so what's shown always matches the
        # coordinates actually being used for routing.
        address = geocode_result.resolved_address or request.address

    store.name = request.name
    store.address = address
    store.coordinates = coordinates
    store.approximate_location = approximate_location
    store.time_window_start = request.time_window_start
    store.time_window_end = request.time_window_end
    store.case_count = request.case_count
    store.delivery_date = request.delivery_date
    save_stores()
    return store


@router.delete("/stores/{store_id}")
def delete_store(store_id: str) -> dict[str, bool]:
    store = next((s for s in STORES if s.id == store_id), None)
    if store is None:
        raise HTTPException(status_code=404, detail="Unknown store id")
    STORES.remove(store)
    save_stores()
    return {"ok": True}


@router.delete("/stores")
def delete_all_stores() -> dict[str, int]:
    count = len(STORES)
    STORES.clear()
    save_stores()
    return {"deleted": count}


@router.get("/drivers", response_model=list[Driver])
def list_drivers() -> list[Driver]:
    return DRIVERS


@router.post("/optimize", response_model=OptimizeResponse)
def optimize(request: OptimizeRequest) -> OptimizeResponse:
    if request.store_ids is None:
        stores = STORES
    else:
        by_id = {s.id: s for s in STORES}
        missing = [i for i in request.store_ids if i not in by_id]
        if missing:
            raise HTTPException(status_code=404, detail=f"Unknown store ids: {missing}")
        stores = [by_id[i] for i in request.store_ids]

    if request.driver_ids is None:
        drivers = DRIVERS
    else:
        driver_by_id = {d.id: d for d in DRIVERS}
        missing_drivers = [i for i in request.driver_ids if i not in driver_by_id]
        if missing_drivers:
            raise HTTPException(status_code=404, detail=f"Unknown driver ids: {missing_drivers}")
        drivers = [driver_by_id[i] for i in request.driver_ids]

    if not drivers:
        raise HTTPException(status_code=400, detail="No driver selected. Add a driver before optimizing routes.")

    routes, unassigned = build_routes(drivers, stores)
    return OptimizeResponse(routes=routes, unassigned_store_ids=unassigned)


@router.post("/routes/reorder", response_model=DriverRoute)
def reorder_route(request: ReorderRouteRequest) -> DriverRoute:
    driver = next((d for d in DRIVERS if d.id == request.driver_id), None)
    if driver is None:
        raise HTTPException(status_code=404, detail="Unknown driver id")

    by_id = {s.id: s for s in STORES}
    missing = [i for i in request.store_ids if i not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown store ids: {missing}")

    ordered = [by_id[i] for i in request.store_ids]
    return build_route_for_order(driver, ordered)


@router.post("/routes/resequence", response_model=DriverRoute)
def resequence_route(request: ResequenceRouteRequest) -> DriverRoute:
    driver = next((d for d in DRIVERS if d.id == request.driver_id), None)
    if driver is None:
        raise HTTPException(status_code=404, detail="Unknown driver id")

    by_id = {s.id: s for s in STORES}
    missing = [i for i in request.store_ids if i not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown store ids: {missing}")

    stores = [by_id[i] for i in request.store_ids]
    ordered = order_for_strategy(request.strategy, driver, stores)
    return build_route_for_order(driver, ordered)
