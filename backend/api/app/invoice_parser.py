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
# "123 Main St, Suite 4B, Chicago, IL 60601" — a street number through a
# 5-digit zip. Punctuation (commas, periods, apostrophes, "#", "&", "-") is
# optional throughout since OCR frequently drops or garbles it, and unit
# numbers ("Suite 4B") mean digits can appear in the street segment too.
_ADDRESS_RE = re.compile(
    r"\d{1,6}\s+[A-Za-z0-9.,'#&\-\s]+?,?\s*[A-Za-z0-9.,'#&\-\s]+?,?\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?",
)
# Case quantities on beverage distributor invoices are conventionally
# written per line item as "6/CS", "12 CS", etc. — sum every match found
# rather than trying to parse a line-item table (OCR text rarely preserves
# clean column alignment).
_CASE_QTY_RE = re.compile(r"(\d+)\s*/?\s*CS\b", re.IGNORECASE)


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
    ship_to_anchor = _SHIP_TO_ANCHOR_RE.search(text)
    if ship_to_anchor:
        window = text[ship_to_anchor.end() : ship_to_anchor.end() + _SHIP_TO_WINDOW]
        window_match = _ADDRESS_RE.search(window)
        if window_match:
            address_match = window_match

    address = re.sub(r"\s+", " ", address_match.group(0)).strip() if address_match else None

    return {
        "invoice_number": invoice_match.group(1).strip(" .-") if invoice_match else None,
        "address": address,
        "location": _extract_location(text, last_address_match),
        "case_count": sum(int(n) for n in case_matches) if case_matches else None,
    }


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
