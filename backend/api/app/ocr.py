import os
from pathlib import Path

import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from pypdf import PdfReader


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        text = _extract_pdf_text_layer(path)
        if text.strip():
            return text
        # No embedded text layer -- a scanned/image-only PDF. Falls back to
        # OCR, which needs the tesseract/poppler system binaries, so this
        # path only works when those are installed (e.g. local dev, not
        # Vercel). Most invoice PDFs are text-based and never reach here.
        return _ocr_pdf(path)
    return _ocr_image(path)


def _extract_pdf_text_layer(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _tesseract_cmd() -> str | None:
    # Read lazily (not at import time) so this always sees the env vars
    # load_dotenv() populates in main.py, regardless of import order.
    return os.getenv("TESSERACT_CMD")


def _ocr_pdf(path: Path) -> str:
    tesseract_cmd = _tesseract_cmd()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    poppler_path = os.getenv("POPPLER_PATH") or None
    pages = convert_from_path(str(path), poppler_path=poppler_path)
    return "\n".join(pytesseract.image_to_string(page) for page in pages)


def _ocr_image(path: Path) -> str:
    tesseract_cmd = _tesseract_cmd()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    with Image.open(path) as image:
        return pytesseract.image_to_string(image)
