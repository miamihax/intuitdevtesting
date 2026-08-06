import base64
import hashlib
import hmac
import os
import time
from urllib.parse import urlencode

import httpx

from .qbo_tokens import QBOTokens, load_tokens, save_tokens

_AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
_SCOPE = "com.intuit.quickbooks.accounting"

# Refresh a little before actual expiry so the access token used for a
# request doesn't die mid-flight.
_EXPIRY_SAFETY_MARGIN_SECONDS = 60


class NotConnectedError(RuntimeError):
    pass


def _api_base() -> str:
    environment = os.getenv("QBO_ENVIRONMENT", "sandbox")
    if environment == "production":
        return "https://quickbooks.api.intuit.com"
    return "https://sandbox-quickbooks.api.intuit.com"


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": os.getenv("QBO_CLIENT_ID", ""),
        "response_type": "code",
        "scope": _SCOPE,
        "redirect_uri": os.getenv("QBO_REDIRECT_URI", ""),
        "state": state,
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


def _store_token_response(payload: dict, realm_id: str) -> QBOTokens:
    now = time.time()
    tokens: QBOTokens = {
        "realm_id": realm_id,
        "access_token": payload["access_token"],
        "refresh_token": payload["refresh_token"],
        "access_token_expires_at": now + payload["expires_in"],
        "refresh_token_expires_at": now + payload["x_refresh_token_expires_in"],
    }
    save_tokens(tokens)
    return tokens


def _request_tokens(data: dict) -> dict:
    client_id = os.getenv("QBO_CLIENT_ID", "")
    client_secret = os.getenv("QBO_CLIENT_SECRET", "")
    response = httpx.post(
        _TOKEN_URL,
        data=data,
        auth=(client_id, client_secret),
        headers={"Accept": "application/json"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def exchange_code_for_tokens(code: str, realm_id: str) -> QBOTokens:
    redirect_uri = os.getenv("QBO_REDIRECT_URI", "")
    payload = _request_tokens(
        {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri}
    )
    return _store_token_response(payload, realm_id)


def _refresh_access_token(tokens: QBOTokens) -> QBOTokens:
    payload = _request_tokens({"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]})
    return _store_token_response(payload, tokens["realm_id"])


def get_valid_access_token() -> tuple[str, str]:
    """Returns (access_token, realm_id), refreshing first if needed."""
    tokens = load_tokens()
    if tokens is None:
        raise NotConnectedError("QuickBooks isn't connected yet — visit /api/quickbooks/connect")
    if time.time() >= tokens["access_token_expires_at"] - _EXPIRY_SAFETY_MARGIN_SECONDS:
        tokens = _refresh_access_token(tokens)
    return tokens["access_token"], tokens["realm_id"]


def fetch_invoice(invoice_id: str) -> dict:
    access_token, realm_id = get_valid_access_token()
    response = httpx.get(
        f"{_api_base()}/v3/company/{realm_id}/invoice/{invoice_id}",
        params={"minorversion": "65"},
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()["Invoice"]


def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Intuit signs the raw payload with the app's Webhooks "Verifier Token"
    (HMAC-SHA256, base64-encoded) and sends it as the intuit-signature header."""
    verifier_token = os.getenv("QBO_WEBHOOK_VERIFIER_TOKEN", "")
    if not verifier_token or not signature_header:
        return False
    digest = hmac.new(verifier_token.encode(), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature_header)


def _format_address(addr: dict | None) -> str | None:
    if not addr:
        return None
    state_zip = " ".join(p for p in [addr.get("CountrySubDivisionCode"), addr.get("PostalCode")] if p)
    parts = [p for p in [addr.get("Line1"), addr.get("City"), state_zip] if p]
    return ", ".join(parts) if parts else None


def _total_line_quantity(invoice: dict) -> int | None:
    total = 0
    found = False
    for line in invoice.get("Line", []):
        detail = line.get("SalesItemLineDetail")
        if detail and "Qty" in detail:
            total += int(detail["Qty"])
            found = True
    return total if found else None


def invoice_to_pending_fields(invoice: dict) -> dict[str, str | int | None]:
    address = _format_address(invoice.get("ShipAddr")) or _format_address(invoice.get("BillAddr"))
    return {
        "invoice_number": invoice.get("DocNumber"),
        "name": (invoice.get("CustomerRef") or {}).get("name"),
        "address": address,
        "case_count": _total_line_quantity(invoice),
    }
