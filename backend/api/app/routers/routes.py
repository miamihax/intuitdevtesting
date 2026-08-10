from fastapi import APIRouter, HTTPException

from ..data import DRIVERS, STORES, save_stores
from ..models import Driver, OptimizeRequest, OptimizeResponse, Store
from ..optimizer import build_routes

router = APIRouter(prefix="/api")


@router.get("/stores", response_model=list[Store])
def list_stores() -> list[Store]:
    return STORES


@router.delete("/stores/{store_id}")
def delete_store(store_id: str) -> dict[str, bool]:
    store = next((s for s in STORES if s.id == store_id), None)
    if store is None:
        raise HTTPException(status_code=404, detail="Unknown store id")
    STORES.remove(store)
    save_stores()
    return {"ok": True}


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

    routes, unassigned = build_routes(drivers, stores)
    return OptimizeResponse(routes=routes, unassigned_store_ids=unassigned)
