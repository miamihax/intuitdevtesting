import threading

from .models import Settings
from .paths import DATA_DIR

# Persisted to disk so preferences survive a backend restart — same
# DATA_DIR pattern as office.py.
_SETTINGS_PATH = DATA_DIR / "settings.json"
_lock = threading.Lock()


def get_settings() -> Settings:
    with _lock:
        if _SETTINGS_PATH.exists():
            return Settings.model_validate_json(_SETTINGS_PATH.read_text())
        return Settings()


def update_settings(settings: Settings) -> Settings:
    with _lock:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_PATH.write_text(settings.model_dump_json())
    return settings
