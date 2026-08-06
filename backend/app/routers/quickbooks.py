import logging
import secrets

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import quickbooks as qbo
from ..geocode import geocode_address
from ..import_store import PendingImport, add_pending, get_pending, pop_pending, update_pending
from ..qbo_tokens import load_tokens

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


def _process_invoice_event(invoice_id: str, operation: str) -> None:
    pending_id = f"qbo-{invoice_id}"

    if operation == "Delete":
        pop_pending(pending_id)
        return

    if get_pending(pending_id) is None:
        add_pending(
            PendingImport(
                id=pending_id,
                file_name=f"QuickBooks Invoice ({invoice_id})",
                source="quickbooks",
                status="processing",
            )
        )

    try:
        invoice = qbo.fetch_invoice(invoice_id)
        fields = qbo.invoice_to_pending_fields(invoice)
        address = fields.get("address")
        coordinates = geocode_address(address) if address else None
        update_pending(
            pending_id,
            status="ready",
            file_name=f"QuickBooks Invoice #{fields.get('invoice_number') or invoice_id}",
            invoice_number=fields.get("invoice_number"),
            name=fields.get("name"),
            address=address,
            coordinates=coordinates,
            case_count=fields.get("case_count"),
        )
    except Exception as exc:  # a bad/unreachable invoice must not take down the webhook handler
        logger.exception("Failed to process QuickBooks invoice %s", invoice_id)
        update_pending(pending_id, status="error", error=str(exc))


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
