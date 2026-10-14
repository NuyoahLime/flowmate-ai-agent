from fastapi import APIRouter, HTTPException

from flowmate.demo import demo_mode_enabled
from flowmate.persistence import SQLiteTaskRepository
from flowmate.tools import (
    RuntimeToolConfigurationError,
    runtime_provider_status,
    runtime_tool_mode_from_env,
)


router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/status")
def system_status():
    try:
        SQLiteTaskRepository()
        database_ready = True
    except Exception:
        database_ready = False
    try:
        tool_mode = runtime_tool_mode_from_env().value
        providers = runtime_provider_status()
    except RuntimeToolConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Tool provider unavailable: {exc}",
        ) from exc

    return {
        "backend_ready": True,
        "database_ready": database_ready,
        "demo_mode": demo_mode_enabled(),
        "tool_mode": tool_mode,
        "providers": providers,
        "integrations": {
            "google_calendar": {"status": "verified"},
            "open_meteo": {"status": "verified"},
            "amap": {"status": "verified"},
            "feishu": {"status": "engineering_ready_real_pending"},
        },
    }
