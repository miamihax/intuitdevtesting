import json
import threading
from typing import TypedDict

from .paths import DATA_DIR

# Lives alongside the OCR import pipeline's uploaded/processed files — see
# app/paths.py for why the actual directory differs between local dev and
# Vercel (whose filesystem is read-only outside /tmp).
_TOKENS_PATH = DATA_DIR / "qbo_tokens.json"
_lock = threading.Lock()


class QBOTokens(TypedDict):
    realm_id: str
    access_token: str
    refresh_token: str
    access_token_expires_at: float  # unix timestamp
    refresh_token_expires_at: float  # unix timestamp


def save_tokens(tokens: QBOTokens) -> None:
    with _lock:
        _TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TOKENS_PATH.write_text(json.dumps(tokens))


def load_tokens() -> QBOTokens | None:
    with _lock:
        if not _TOKENS_PATH.exists():
            return None
        return json.loads(_TOKENS_PATH.read_text())


def clear_tokens() -> None:
    with _lock:
        _TOKENS_PATH.unlink(missing_ok=True)
