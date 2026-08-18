import re

# The captured token must contain at least one digit (via lookahead) so a
# bare "Invoice" document title followed by an unrelated word (e.g. a
# "Date" label on the next line) doesn't get mistaken for the number.
_INVOICE_NUMBER_RE = re.compile(
    r"invoice\s*(?:number|no\.?|#)?\s*[:#]?\s*(?=[A-Z0-9\-.]*\d)([A-Z0-9][A-Z0-9\-.]{2,})",
    re.IGNORECASE,
)
# Anchored to the start of a line and requires a ":"/"-" delimiter, so a
# label word that just happens to appear in running text (e.g. a business
# name ending in "Store") can't be mistaken for a "Store:" label — and the
# capture can't run past its own line into whatever follows.
_LOCATION_LABEL_RE = re.compile(
    r"^[ \t]*(?:ship\s*to|deliver\s*to|location|store)[ \t]*[:\-][ \t]*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
# Packing slips commonly draw "Ship To" as a boxed section header with
# nothing after it on the same line — the company name is the first line
# inside the box, i.e. the next non-blank line beneath the header. Limited
# to "ship to"/"deliver to" (not the bare "store"/"location" words, which
# are too likely to appear standalone in unrelated text).
_LOCATION_HEADER_RE = re.compile(
    r"^[ \t]*(?:ship\s*to|deliver\s*to)[ \t]*[:\-]?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
# Matches the "Ship To"/"Deliver To" line itself (inline value or bare
# header, either way), used to scope the address search below.
_SHIP_TO_ANCHOR_RE = re.compile(
    r"^[ \t]*(?:ship\s*to|deliver\s*to)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
# How far past the "Ship To" line to look for the delivery address. Wide
# enough to cover a boxed section (name, street, city/state/zip, phone)
# but narrow enough to not run into unrelated content further down.
_SHIP_TO_WINDOW = 300
# Same idea as _SHIP_TO_ANCHOR_RE/_SHIP_TO_WINDOW, but for the "Bill To"
# section -- used as a fallback geocoding candidate when the delivery
# address itself doesn't resolve to a precise location (small independent
# stores often bill and ship to the same place, even when their printed
# delivery address is malformed or too sparse for a geocoder).
_BILL_TO_ANCHOR_RE = re.compile(
    r"^[ \t]*bill\s*to\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_BILL_TO_WINDOW = 300
# "123 Main St, Suite 4B, Chicago, IL 60601" — a street number through a
# 5-digit zip. Punctuation (commas, periods, apostrophes, "#", "&", "-") is
# optional throughout since OCR frequently drops or garbles it, and unit
# numbers ("Suite 4B") mean digits can appear in the street segment too. The
# house number can carry a unit letter with no space before the street name
# ("25C WASHINGTON ST") -- without allowing that, this fails to match the
# real address entirely, and the search below latches onto unrelated
# digit-then-state-zip text further down the page instead (a phone number,
# another party's address block, ...).
_ADDRESS_RE = re.compile(
    r"\d{1,6}[A-Za-z]?\s+[A-Za-z0-9.,'#&\-\s]+?,?\s*[A-Za-z0-9.,'#&\-\s]+?,?\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?",
)
# Each line item's "N/CS" (e.g. "6/CS") states the *pack size* -- how many
# bottles per case -- not how many cases were ordered. The actual ordered
# quantity is the invoice's Quantity column, which text extraction runs
# together directly against that same "CS" with no separator (e.g.
# "6/CS1 120.00 120.00" -- pack size 6/case, quantity ordered 1). Sum the
# digits immediately following each "CS" rather than the pack size itself.
_CASE_QTY_RE = re.compile(r"CS(\d+)", re.IGNORECASE)
# The customer's phone number line inside the Ship To box (e.g.
# "PH: 201-840-0777"), used only as an anchor to find the delivery-window
# note conventionally scrawled on the line right beneath it.
_PHONE_LINE_RE = re.compile(
    r"^[ \t]*(?:ph|phone|tel)\.?\s*#?[ \t]*[:\-]?[ \t]*[\d()\-.\s]{7,}$",
    re.IGNORECASE | re.MULTILINE,
)
# Clock times within a delivery-window note — "2PM", "10:30 am", etc.
_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([AaPp])\.?[Mm]\.?")


def parse_invoice_fields(text: str) -> dict[str, str | int | None]:
    invoice_match = _INVOICE_NUMBER_RE.search(text)
    case_matches = _CASE_QTY_RE.findall(text)

    # Packing slips/invoices typically list the distributor's own letterhead
    # address near the top and the actual delivery destination further down
    # — prefer the last address-shaped match in the document over the first.
    address_matches = list(_ADDRESS_RE.finditer(text))
    last_address_match = address_matches[-1] if address_matches else None

    # When there's an explicit "Ship To" section, prefer whatever address
    # appears inside it over the whole-document heuristic above — invoices
    # that also print a "Bill To" box, or put the distributor's own address
    # after the Ship To box in the raw text, would otherwise pick the wrong
    # address.
    address_match = last_address_match
    time_window_start: str | None = None
    time_window_end: str | None = None
    ship_to_anchor = _SHIP_TO_ANCHOR_RE.search(text)
    if ship_to_anchor:
        window = text[ship_to_anchor.end() : ship_to_anchor.end() + _SHIP_TO_WINDOW]
        window_match = _ADDRESS_RE.search(window)
        if window_match:
            address_match = window_match
        time_window_start, time_window_end = _extract_delivery_window(window)

    address = re.sub(r"\s+", " ", address_match.group(0)).strip() if address_match else None

    bill_to_address = None
    bill_to_anchor = _BILL_TO_ANCHOR_RE.search(text)
    if bill_to_anchor:
        bill_window = text[bill_to_anchor.end() : bill_to_anchor.end() + _BILL_TO_WINDOW]
        bill_window_match = _ADDRESS_RE.search(bill_window)
        if bill_window_match:
            bill_to_address = re.sub(r"\s+", " ", bill_window_match.group(0)).strip()

    return {
        "invoice_number": invoice_match.group(1).strip(" .-") if invoice_match else None,
        "address": address,
        "bill_to_address": bill_to_address if bill_to_address != address else None,
        "location": _extract_location(text, last_address_match),
        "case_count": sum(int(n) for n in case_matches) if case_matches else None,
        "time_window_start": time_window_start,
        "time_window_end": time_window_end,
    }


def _extract_delivery_window(window: str) -> tuple[str | None, str | None]:
    phone_match = _PHONE_LINE_RE.search(window)
    if phone_match is None:
        return None, None
    for line in window[phone_match.end() :].splitlines():
        line = line.strip()
        if line:
            return _parse_delivery_window(line)
    return None, None


def _parse_delivery_window(note: str) -> tuple[str | None, str | None]:
    times = [_to_24h(hour, minute, meridiem) for hour, minute, meridiem in _TIME_RE.findall(note)]
    if not times:
        return None, None
    if len(times) >= 2:
        return times[0], times[1]
    if re.search(r"\bafter\b", note, re.IGNORECASE):
        return times[0], None
    # A single time with no "after" ("DELIVER BEFORE 2PM!!", or just "2PM")
    # reads as a delivery deadline, not an earliest-arrival time.
    return None, times[0]


def _to_24h(hour: str, minute: str, meridiem: str) -> str:
    h = int(hour) % 12
    if meridiem.lower() == "p":
        h += 12
    return f"{h:02d}:{minute or '00'}"


def _extract_location(text: str, address_match: re.Match[str] | None) -> str | None:
    label_match = _LOCATION_LABEL_RE.search(text)
    if label_match:
        return label_match.group(1).strip()

    header_match = _LOCATION_HEADER_RE.search(text)
    if header_match:
        for line in text[header_match.end():].splitlines():
            line = line.strip()
            if line:
                return line

    if address_match is None:
        return None
    # No explicit "ship to"/"store" label — the customer's name is
    # conventionally the line right above their address on a packing slip.
    # Skip past a line that's itself just a label (e.g. "PICKED BY:").
    preceding_lines = [line.strip() for line in text[: address_match.start()].splitlines() if line.strip()]
    for line in reversed(preceding_lines):
        if line.endswith(":"):
            continue
        return line
    return None
