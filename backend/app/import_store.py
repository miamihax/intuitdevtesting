import threading

from .models import PendingImport

# The upload endpoint (request thread) and the watchdog observer (its own
# background thread) both mutate this, so every access goes through the lock.
_lock = threading.Lock()
_pending: dict[str, PendingImport] = {}


def add_pending(item: PendingImport) -> None:
    with _lock:
        _pending[item.id] = item


def update_pending(pending_id: str, **fields: object) -> None:
    with _lock:
        current = _pending.get(pending_id)
        if current is None:
            return
        _pending[pending_id] = current.model_copy(update=fields)


def list_pending() -> list[PendingImport]:
    with _lock:
        return list(_pending.values())


def get_pending(pending_id: str) -> PendingImport | None:
    with _lock:
        return _pending.get(pending_id)


def pop_pending(pending_id: str) -> PendingImport | None:
    with _lock:
        return _pending.pop(pending_id, None)
