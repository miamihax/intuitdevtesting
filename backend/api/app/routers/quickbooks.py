import logging
import secrets

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import quickbooks as qbo
from ..geocode import geocode_address
from ..import_store import PendingImport, add_pending, get_pending, pop_pending, update_pending
from ..models import Store
from ..orders import add_store
from ..qbo_tokens import load_tokens
from ..settings_store import get_settings

router = APIRouter(prefix="/api/quickbooks")
logger = logging.getLogger(__name__)

# CSRF guard for the OAuth redirect — Intuit echoes `state` back on the
# callback, and we reject callbacks that don't match something we issued.
_pending_states: set[str] = set()


@router.get("/status")
def status() -> dict[str, bool | str | None]:
    tokens = load_tokens()
    return {"connected": tokens is not None, "realm_id": tokens["realm_id"] if tokens else None}


@router.get("/connect")
def connect() -> RedirectResponse:
    state = secrets.token_urlsafe(16)
    _pending_states.add(state)
    return RedirectResponse(qbo.build_authorize_url(state))


@router.get("/callback")
def callback(code: str, state: str, realmId: str) -> HTMLResponse:
    if state not in _pending_states:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    _pending_states.discard(state)
    qbo.exchange_code_for_tokens(code, realmId)
    return HTMLResponse("<html><body><h3>QuickBooks connected — you can close this tab.</h3></body></html>")


def _upsert_pending_from_invoice(invoice_id: str, invoice: dict) -> PendingImport | Store:
    """Maps an already-fetched QBO invoice onto a PendingImport (or, when
    auto-add is on and enough was extracted, straight into a confirmed
    Store). Shared by the webhook path (which fetches the invoice via
    OAuth) and the manual import-invoice endpoint (which is handed the
    invoice JSON directly)."""
    pending_id = f"qbo-{invoice_id}"
    if get_pending(pending_id) is None:
        add_pending(
            PendingImport(
                id=pending_id,
                file_name=f"QuickBooks Invoice ({invoice_id})",
                source="quickbooks",
                status="processing",
            )
        )

    fields = qbo.invoice_to_pending_fields(invoice)
    address = fields.get("address")
    name = fields.get("name")
    geocode_result = geocode_address(address) if address else None

    # See import_watcher.py for the matching upload-side logic -- auto-add
    # only fires when there's enough to stand on its own; anything short of
    # that still needs a human, so it falls through to the pending queue.
    if get_settings().auto_add_imports and name and address and geocode_result is not None:
        store = add_store(
            invoice_number=fields.get("invoice_number"),
            name=name,
            address=address,
            coordinates=geocode_result.coordinates,
            approximate_location=geocode_result.approximate,
            time_window_start=None,
            time_window_end=None,
            case_count=fields.get("case_count"),
        )
        pop_pending(pending_id)
        return store

    update_pending(
        pending_id,
        status="ready",
        file_name=f"QuickBooks Invoice #{fields.get('invoice_number') or invoice_id}",
        invoice_number=fields.get("invoice_number"),
        name=name,
        address=address,
        coordinates=geocode_result.coordinates if geocode_result else None,
        approximate_location=geocode_result.approximate if geocode_result else False,
        case_count=fields.get("case_count"),
    )
    pending = get_pending(pending_id)
    assert pending is not None
    return pending


def _process_invoice_event(invoice_id: str, operation: str) -> None:
    pending_id = f"qbo-{invoice_id}"

    if operation == "Delete":
        pop_pending(pending_id)
        return

    try:
        invoice = qbo.fetch_invoice(invoice_id)
        _upsert_pending_from_invoice(invoice_id, invoice)
    except Exception as exc:  # a bad/unreachable invoice must not take down the webhook handler
        logger.exception("Failed to process QuickBooks invoice %s", invoice_id)
        if get_pending(pending_id) is None:
            add_pending(
                PendingImport(
                    id=pending_id,
                    file_name=f"QuickBooks Invoice ({invoice_id})",
                    source="quickbooks",
                    status="error",
                    error=str(exc),
                )
            )
        else:
            update_pending(pending_id, status="error", error=str(exc))


@router.post("/import-invoice", response_model=PendingImport | Store)
def import_invoice(invoice: dict) -> PendingImport | Store:
    """Accepts a QuickBooks invoice JSON directly (e.g. fetched via the
    QuickBooks MCP server) and drops it into the pending-imports queue —
    the same destination the webhook path feeds, minus the OAuth round trip.
    Useful for testing the pipeline without a full Intuit webhook setup."""
    invoice_id = invoice.get("Id")
    if not invoice_id:
        raise HTTPException(status_code=422, detail='Invoice JSON is missing an "Id" field')
    return _upsert_pending_from_invoice(invoice_id, invoice)


@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, bool]:
    raw_body = await request.body()
    if not qbo.verify_webhook_signature(raw_body, request.headers.get("intuit-signature")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    for notification in payload.get("eventNotifications", []):
        for entity in notification.get("dataChangeEvent", {}).get("entities", []):
            if entity.get("name") != "Invoice":
                continue
            invoice_id = entity.get("id")
            if invoice_id:
                background_tasks.add_task(_process_invoice_event, invoice_id, entity.get("operation", ""))

    # Intuit expects a fast 200 — fetching the invoice and geocoding its
    # address happen after we've already responded.
    return {"received": True}
