import time
import uuid
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .geocode import geocode_address, suggest_address_via_web
from .import_store import PendingImport, add_pending, pop_pending, update_pending
from .invoice_parser import parse_invoice_fields
from .ocr import extract_text
from .orders import add_store
from .paths import DATA_DIR
from .settings_store import get_settings

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
            name = fields.get("location")
            # Web search is a human-reviewed suggestion here, not something
            # applied automatically -- keep it out of the main geocode call
            # (use_web_fallback=False) and fetch it separately below.
            geocode_result = geocode_address(address, name, use_web_fallback=False) if address else None
            # A name search can land on a different (correct) address than
            # what OCR read off the invoice -- prefer that over the raw
            # OCR'd text so what's shown always matches the coordinates.
            resolved_address = (geocode_result.resolved_address if geocode_result else None) or address

            suggested_address = None
            suggested_address_source = None
            if name and address and (geocode_result is None or geocode_result.approximate):
                # Small independent stores often bill and ship to the same
                # place -- try the invoice's Bill To address before falling
                # back to a generic web search, since it's real data off
                # the document itself rather than a guess.
                bill_to_address = fields.get("bill_to_address")
                if bill_to_address:
                    bill_result = geocode_address(bill_to_address, name, use_web_fallback=False)
                    if bill_result is not None and not bill_result.approximate:
                        suggested_address = bill_result.resolved_address or bill_to_address
                        suggested_address_source = "bill_to"

                if suggested_address is None:
                    web_result = suggest_address_via_web(address, name)
                    if web_result is not None:
                        suggested_address = web_result.resolved_address
                        suggested_address_source = "web_search"

            # Auto-add only fires when OCR extracted enough to stand on its
            # own (a name, an address, and an exact geocode) -- a ZIP-centroid
            # fallback match (geocode_result.approximate) means the exact
            # address wasn't found, so that -- like anything else short of
            # a full match -- still needs a human to confirm the location,
            # falling through to the normal "ready for review" pending card.
            if (
                get_settings().auto_add_imports
                and name
                and address
                and geocode_result is not None
                and not geocode_result.approximate
            ):
                add_store(
                    invoice_number=fields.get("invoice_number"),
                    name=name,
                    address=resolved_address,
                    coordinates=geocode_result.coordinates,
                    approximate_location=geocode_result.approximate,
                    time_window_start=fields.get("time_window_start"),
                    time_window_end=fields.get("time_window_end"),
                    case_count=fields.get("case_count"),
                )
                pop_pending(pending_id)
            else:
                update_pending(
                    pending_id,
                    status="ready",
                    invoice_number=fields.get("invoice_number"),
                    name=name,
                    address=resolved_address,
                    coordinates=geocode_result.coordinates if geocode_result else None,
                    approximate_location=geocode_result.approximate if geocode_result else False,
                    suggested_address=suggested_address,
                    suggested_address_source=suggested_address_source,
                    case_count=fields.get("case_count"),
                    time_window_start=fields.get("time_window_start"),
                    time_window_end=fields.get("time_window_end"),
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
