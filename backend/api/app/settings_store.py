import threading

from .blob_store import load_json, save_json, using_blob
from .models import Settings
from .paths import DATA_DIR

# Persisted to disk so preferences survive a backend restart — same
# DATA_DIR pattern as office.py. On Vercel this goes to Blob storage instead
# — see blob_store.py.
_SETTINGS_PATH = DATA_DIR / "settings.json"
_lock = threading.Lock()


def get_settings() -> Settings:
    with _lock:
        if using_blob():
            raw = load_json("settings.json")
            return Settings.model_validate(raw) if raw is not None else Settings()
        if _SETTINGS_PATH.exists():
            return Settings.model_validate_json(_SETTINGS_PATH.read_text())
        return Settings()


def update_settings(settings: Settings) -> Settings:
    with _lock:
        if using_blob():
            save_json("settings.json", settings.model_dump())
        else:
            _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _SETTINGS_PATH.write_text(settings.model_dump_json())
    return settings
