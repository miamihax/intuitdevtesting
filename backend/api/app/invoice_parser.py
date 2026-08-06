import re

_INVOICE_NUMBER_RE = re.compile(
    r"invoice\s*(?:number|no\.?|#)?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-.]{2,})",
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
    address_match = address_matches[-1] if address_matches else None

    address = re.sub(r"\s+", " ", address_match.group(0)).strip() if address_match else None

    return {
        "invoice_number": invoice_match.group(1).strip(" .-") if invoice_match else None,
        "address": address,
        "location": _extract_location(text, address_match),
        "case_count": sum(int(n) for n in case_matches) if case_matches else None,
    }


def _extract_location(text: str, address_match: re.Match[str] | None) -> str | None:
    label_match = _LOCATION_LABEL_RE.search(text)
    if label_match:
        return label_match.group(1).strip()

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
