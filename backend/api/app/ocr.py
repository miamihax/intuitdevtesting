import os
from pathlib import Path

import pytesseract
from PIL import Image
from pdf2image import convert_from_path


def extract_text(path: Path) -> str:
    # Read lazily (not at import time) so this always sees the env vars
    # load_dotenv() populates in main.py, regardless of import order.
    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    poppler_path = os.getenv("POPPLER_PATH") or None

    if path.suffix.lower() == ".pdf":
        pages = convert_from_path(str(path), poppler_path=poppler_path)
        return "\n".join(pytesseract.image_to_string(page) for page in pages)
    with Image.open(path) as image:
        return pytesseract.image_to_string(image)
