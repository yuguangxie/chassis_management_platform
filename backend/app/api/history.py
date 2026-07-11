from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.api.data_source import dashboard_metadata
from app.api.errors import get_trace_id
from app.api.models import (
    ActionResponse,
    HistoryDashboardResponse,
    HistoryExportRequest,
    ReplaySeekRequest,
    ObjectListResponse,
    ObjectResponse,
)
from app.security.auth import Principal, Role, require_role
from app.services.app_state import state
from app.services.audit import record_operator_action
from app.services.file_access import validate_file_id


router = APIRouter()


def _service():
    if state.history_service is None:
        from fastapi import HTTPException

        raise HTTPException(503, {"code": "HISTORY_SERVICE_UNAVAILABLE", "message": "历史服务未初始化", "details": {}})
    return state.history_service


def _filter_payload(
    chassis_no: str | None = None,
    vin: str | None = None,
    serial_no: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    result: str | None = None,
    operator: str | None = None,
    station: str | None = None,
) -> dict[str, Any]:
    return {
        "chassis_no": chassis_no,
        "vin": vin,
        "serial_no": serial_no,
        "start_time": start_time,
        "end_time": end_time,
        "result": result,
        "operator": operator,
        "station": station,
    }


@router.get("/history/dashboard", response_model=HistoryDashboardResponse)
async def dashboard(
    chassis_no: str | None = None,
    vin: str | None = None,
    serial_no: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    result: str | None = None,
    operator: str | None = None,
    station: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return _service().dashboard(
        page=page,
        page_size=page_size,
        **_filter_payload(chassis_no, vin, serial_no, start_time, end_time, result, operator, station),
    )


@router.get("/history/statistics", response_model=ObjectResponse)
async def statistics(vin: str | None = None):
    _, total = _service().sessions(page=1, page_size=1)
    return {
        "summary": _service().summary(total),
        "charts": _service().charts(vin),
        "pagination": {"page": 1, "page_size": 20, "total": total, "total_pages": (total + 19) // 20 if total else 0},
        **dashboard_metadata("sqlite", quality="good"),
    }


@router.post("/history/export", response_model=ActionResponse)
async def export_history(
    payload: HistoryExportRequest,
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    path = _service().export_history(payload.model_dump())
    details = _service().export_metadata(path)
    record_operator_action(state, principal, "export_history", path.name, payload.model_dump(), trace_id=get_trace_id())
    return {"ok": True, "message": "历史查询结果已导出", "trace_id": get_trace_id(), "details": details}


@router.get("/history/exports/{file_id}")
async def download_history_export(
    file_id: str,
    principal: Principal = Depends(require_role(Role.VIEWER)),
):
    validate_file_id(file_id)
    path = _service().history_export_path(file_id)
    record_operator_action(state, principal, "download_history_export", file_id, {}, trace_id=get_trace_id())
    return FileResponse(path, filename=path.name, media_type="text/csv", headers={"X-Trace-Id": get_trace_id()})


@router.get("/test-sessions", response_model=ObjectResponse)
async def sessions(
    chassis_no: str | None = None,
    vin: str | None = None,
    serial_no: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    result: str | None = None,
    operator: str | None = None,
    station: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    items, total = _service().sessions(
        page=page,
        page_size=page_size,
        **_filter_payload(chassis_no, vin, serial_no, start_time, end_time, result, operator, station),
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
        **dashboard_metadata("sqlite", quality="good"),
    }


@router.get("/test-sessions/{sid}", response_model=ObjectResponse)
async def session(sid: str):
    row = _service().session_row(sid)
    item = _service().session_item(row)
    return {**item, "duration": _service()._duration(row.get("started_at"), row.get("ended_at")), **dashboard_metadata("sqlite", quality="good")}


@router.get("/test-sessions/{sid}/timeline", response_model=ObjectListResponse)
async def timeline(sid: str):
    return _service().timeline(sid)


@router.get("/test-sessions/{sid}/operator-actions", response_model=ObjectListResponse)
async def session_operator_actions(sid: str):
    return _service().operator_logs(sid)


@router.get("/test-sessions/{sid}/downloads", response_model=ObjectListResponse)
async def session_downloads(sid: str):
    return _service().download_items(sid)


@router.get("/test-sessions/{sid}/download/{file_type}")
async def session_download(
    sid: str,
    file_type: str,
    principal: Principal = Depends(require_role(Role.VIEWER)),
):
    path = _service().generate_download(sid, file_type)
    record_operator_action(state, principal, "download_session_data", sid, {"file_type": file_type, "file_name": path.name}, trace_id=get_trace_id())
    media = "application/zip" if path.suffix == ".zip" else "application/json" if path.suffix == ".json" else "text/csv"
    return FileResponse(path, filename=path.name, media_type=media, headers={"X-Trace-Id": get_trace_id()})


@router.post("/test-sessions/{sid}/open-detail", response_model=ActionResponse)
async def open_detail(
    sid: str,
    principal: Principal = Depends(require_role(Role.VIEWER)),
):
    _service().session_row(sid)
    record_operator_action(state, principal, "open_session_detail", sid, {}, trace_id=get_trace_id())
    return {"ok": True, "message": "会话详情已载入", "trace_id": get_trace_id(), "details": {"session_id": sid, "route": f"/history?session_id={sid}"}}


@router.get("/test-sessions/{sid}/replay", response_model=ObjectResponse)
async def replay(sid: str):
    return _service().replay(sid)


@router.post("/test-sessions/{sid}/replay/seek", response_model=ObjectResponse)
async def replay_seek(sid: str, payload: ReplaySeekRequest):
    return _service().seek(sid, payload.progress_percent)


@router.get("/test-sessions/{sid}/fault-events", response_model=ObjectListResponse)
async def fault_events(sid: str):
    return _service().fault_events(sid)


@router.get("/audit/operator-actions", response_model=ObjectResponse)
async def actions(_principal: Principal = Depends(require_role(Role.ADMIN))):
    rows = state.database.query("SELECT * FROM operator_actions ORDER BY id DESC LIMIT 100") if state.database else []
    return {"items": rows, "total": len(rows), **dashboard_metadata("sqlite", quality="good" if state.database else "unavailable")}
