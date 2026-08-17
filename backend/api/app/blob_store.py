import json
import os
from typing import Any

import requests
import vercel_blob

# Vercel's filesystem is read-only outside /tmp, and /tmp itself is wiped on
# every cold start (see paths.py) -- so anything written there (drivers,
# stores, settings, QBO tokens) can vanish between one request and the next,
# surfacing as "Unknown driver id" / "Unknown store ids" errors even though
# nothing was actually deleted. Vercel Blob gives each of those JSON files a
# durable home instead. Requires a Blob store connected to the project
# (Storage tab in the Vercel dashboard), which injects BLOB_READ_WRITE_TOKEN.
def using_blob() -> bool:
    return bool(os.getenv("VERCEL"))


def load_json(pathname: str) -> Any | None:
    """Reads a JSON blob by its pathname. Returns None if it doesn't exist yet
    (first run, or nothing saved under that name)."""
    listing = vercel_blob.list()
    blob = next((b for b in listing.get("blobs", []) if b["pathname"] == pathname), None)
    if blob is None:
        return None
    response = requests.get(blob["url"], timeout=10)
    response.raise_for_status()
    return response.json()


def save_json(pathname: str, data: Any) -> None:
    # allowOverwrite is required -- without it, writing to a pathname that
    # already has a blob (i.e. every save after the first) fails outright.
    payload = json.dumps(data).encode("utf-8")
    vercel_blob.put(pathname, payload, {"allowOverwrite": "true"})


def delete_json(pathname: str) -> None:
    listing = vercel_blob.list()
    blob = next((b for b in listing.get("blobs", []) if b["pathname"] == pathname), None)
    if blob is not None:
        vercel_blob.delete([blob["url"]])
