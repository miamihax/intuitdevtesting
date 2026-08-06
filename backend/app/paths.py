import os
from pathlib import Path


def _default_data_dir() -> Path:
    # Vercel functions ship a read-only filesystem except for /tmp — local
    # dev keeps using backend/data/ so nothing changes for that workflow.
    if os.getenv("VERCEL"):
        return Path("/tmp/optiroute-data")
    return Path(__file__).resolve().parent.parent / "data"


DATA_DIR = Path(os.getenv("DATA_DIR") or _default_data_dir())
