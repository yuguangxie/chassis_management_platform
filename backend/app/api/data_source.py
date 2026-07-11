from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.api.errors import get_trace_id
from app.core.time import utc_now
from app.services.app_state import state


def explicit_mock_enabled() -> bool:
    return bool(state.config.profile == "mock" or state.mock_enabled)


def dashboard_metadata(
    data_source: str,
    *,
    quality: str = "good",
    mock: bool | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    is_mock = explicit_mock_enabled() if mock is None else bool(mock)
    return {
        "data_source": "mock" if is_mock else data_source,
        "mock": is_mock,
        "quality": "mock" if is_mock else quality,
        "updated_at": updated_at or utc_now(),
        "trace_id": get_trace_id(),
    }


def require_data_in_production(available: bool, resource: str) -> None:
    if available or state.config.profile != "production":
        return
    raise HTTPException(
        503,
        {
            "code": "PRODUCTION_DATA_UNAVAILABLE",
            "message": f"生产数据不可用：{resource}",
            "details": {"resource": resource, "profile": state.config.profile},
        },
    )
