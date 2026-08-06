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
# "123 Main St, Chicago, IL 60601" — a street number through a 5-digit zip.
# Commas are optional since OCR frequently drops small punctuation.
_ADDRESS_RE = re.compile(
    r"\d{1,6}\s+[A-Za-z0-9.\s]+?,?\s*[A-Za-z\s]+?,?\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?",
)


def parse_invoice_fields(text: str) -> dict[str, str | None]:
    invoice_match = _INVOICE_NUMBER_RE.search(text)
    address_match = _ADDRESS_RE.search(text)
    location_match = _LOCATION_LABEL_RE.search(text)

    return {
        "invoice_number": invoice_match.group(1).strip(" .-") if invoice_match else None,
        "address": address_match.group(0).strip() if address_match else None,
        "location": location_match.group(1).strip() if location_match else None,
    }
