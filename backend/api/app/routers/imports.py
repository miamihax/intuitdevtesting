import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..data import STORES, save_stores
from ..geocode import geocode_address
from ..import_store import PendingImport, add_pending, get_pending, list_pending, pop_pending
from ..import_watcher import INCOMING_DIR
from ..models import ConfirmImportRequest, Store

router = APIRouter(prefix="/api/imports")


@router.post("/upload")
async def upload_invoice(file: UploadFile = File(...)) -> dict[str, str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name")

    pending_id = uuid.uuid4().hex
    add_pending(PendingImport(id=pending_id, file_name=file.filename, status="processing"))

    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    dest = INCOMING_DIR / f"{pending_id}__{file.filename}"
    dest.write_bytes(await file.read())

    return {"pending_id": pending_id}


@router.get("/pending", response_model=list[PendingImport])
def get_pending_imports() -> list[PendingImport]:
    return list_pending()


@router.post("/{pending_id}/confirm", response_model=Store)
def confirm_import(pending_id: str, request: ConfirmImportRequest) -> Store:
    pending = get_pending(pending_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="Unknown pending import")

    # Reuse the geocode captured during OCR unless the address was edited.
    if pending.address == request.address and pending.coordinates is not None:
        coordinates = pending.coordinates
        approximate_location = pending.approximate_location
    else:
        geocode_result = geocode_address(request.address)
        if geocode_result is None:
            raise HTTPException(status_code=422, detail="Could not locate that address — check it and try again")
        coordinates = geocode_result.coordinates
        approximate_location = geocode_result.approximate

    pop_pending(pending_id)

    # Prefer the invoice number as the order ID so it's traceable back to its
    # source document — fall back to a random ID when one wasn't extracted.
    store_id = pending.invoice_number or f"import-{uuid.uuid4().hex[:8]}"

    store = Store(
        id=store_id,
        name=request.name,
        address=request.address,
        coordinates=coordinates,
        approximate_location=approximate_location,
        time_window_start=request.time_window_start,
        time_window_end=request.time_window_end,
        case_count=request.case_count,
    )
    STORES.append(store)
    save_stores()
    return store


@router.post("/{pending_id}/dismiss")
def dismiss_import(pending_id: str) -> dict[str, bool]:
    if pop_pending(pending_id) is None:
        raise HTTPException(status_code=404, detail="Unknown pending import")
    return {"ok": True}
