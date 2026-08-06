import time
import uuid
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .geocode import geocode_address
from .import_store import PendingImport, add_pending, update_pending
from .invoice_parser import parse_invoice_fields
from .ocr import extract_text
from .paths import DATA_DIR

INCOMING_DIR = DATA_DIR / "incoming"
PROCESSED_DIR = DATA_DIR / "processed"


class IncomingInvoiceHandler(FileSystemEventHandler):
    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._process(Path(event.src_path))

    def _process(self, path: Path) -> None:
        # Give the writer (the upload endpoint) a moment to finish flushing.
        time.sleep(0.3)
        if not path.exists():
            return

        # The upload endpoint names files "{pending_id}__{original_name}" so we
        # can update the record it already created. A file with no such prefix
        # (e.g. dropped into the folder by hand) gets tracked fresh here.
        pending_id, sep, original_name = path.name.partition("__")
        if not sep:
            pending_id, original_name = uuid.uuid4().hex, path.name
            add_pending(PendingImport(id=pending_id, file_name=original_name, status="processing"))

        try:
            text = extract_text(path)
            fields = parse_invoice_fields(text)
            address = fields.get("address")
            coordinates = geocode_address(address) if address else None
            update_pending(
                pending_id,
                status="ready",
                invoice_number=fields.get("invoice_number"),
                name=fields.get("location"),
                address=address,
                coordinates=coordinates,
                case_count=fields.get("case_count"),
            )
        except Exception as exc:  # a bad file must not take down the watcher thread
            update_pending(pending_id, status="error", error=str(exc))
        finally:
            PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
            path.rename(PROCESSED_DIR / path.name)


def start_watcher() -> Observer:
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(IncomingInvoiceHandler(), str(INCOMING_DIR), recursive=False)
    observer.start()
    return observer
