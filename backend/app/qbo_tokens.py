import json
import threading
from pathlib import Path
from typing import TypedDict

# Lives under backend/data/, which is entirely gitignored (see .gitignore) —
# same place the OCR import pipeline keeps its uploaded/processed files.
_TOKENS_PATH = Path(__file__).resolve().parent.parent / "data" / "qbo_tokens.json"
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
