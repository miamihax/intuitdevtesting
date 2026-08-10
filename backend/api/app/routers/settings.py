from fastapi import APIRouter

from ..models import Settings
from ..settings_store import get_settings, update_settings

router = APIRouter(prefix="/api/settings")


@router.get("", response_model=Settings)
def read_settings() -> Settings:
    return get_settings()


@router.put("", response_model=Settings)
def write_settings(request: Settings) -> Settings:
    return update_settings(request)
