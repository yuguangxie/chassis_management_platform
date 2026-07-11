from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.api.data_source import dashboard_metadata
from app.api.errors import get_trace_id
from app.api.models import (
    ActionResponse,
    ReportChangeDirectoryRequest,
    ReportDashboardResponse,
    ReportListResponse,
    ReportPreviewResponse,
    ObjectResponse,
)
from app.security.auth import Principal, Role, require_role
from app.services.app_state import state
from app.services.audit import record_operator_action


router = APIRouter()


def _service():
    if state.report_service is None:
        from fastapi import HTTPException

        raise HTTPException(
            503,
            {
                "code": "REPORT_SERVICE_UNAVAILABLE",
                "message": "报告服务未初始化",
                "details": {},
            },
        )
    return state.report_service


def _action(message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "message": message,
        "trace_id": get_trace_id(),
        "data_source": "sqlite+filesystem",
        "mock": False,
        "details": details,
    }


@router.get("/reports/dashboard", response_model=ReportDashboardResponse)
async def dashboard():
    return _service().dashboard()


@router.get("/reports", response_model=ReportListResponse)
async def reports(
    chassis_no: str | None = Query(default=None),
    vin: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    result: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    file_type: str | None = Query(default=None),
):
    items = _service().list_reports(
        chassis_no=chassis_no,
        vin=vin,
        start_time=start_time,
        end_time=end_time,
        result=result,
        operator=operator,
        file_type=file_type,
    )
    return {
        **dashboard_metadata("sqlite+filesystem", quality="good" if items else "unavailable"),
        "items": items,
        "total": len(items),
    }


@router.post("/reports/scan", response_model=ActionResponse)
async def scan(principal: Principal = Depends(require_role(Role.OPERATOR))):
    details = _service().scan()
    record_operator_action(state, principal, "scan_reports", str(_service().output_dir), details, trace_id=get_trace_id())
    return _action("报告目录扫描完成", details)


@router.post("/reports/open-directory", response_model=ActionResponse)
async def open_directory(principal: Principal = Depends(require_role(Role.OPERATOR))):
    path = _service().output_dir
    record_operator_action(state, principal, "open_report_directory", str(path), {}, trace_id=get_trace_id())
    return _action("报告目录已通过安全校验，可由桌面端打开", {"path": str(path), "desktop_action": "openPath"})


@router.post("/reports/change-directory", response_model=ActionResponse)
async def change_directory(
    payload: ReportChangeDirectoryRequest,
    principal: Principal = Depends(require_role(Role.ADMIN)),
):
    path = _service().set_output_dir(payload.path)
    record_operator_action(state, principal, "change_report_directory", str(path), payload.model_dump(), trace_id=get_trace_id())
    return _action("报告目录已切换", {"path": str(path), "active": True})


@router.get("/reports/storage-stats", response_model=ObjectResponse)
async def storage_stats():
    return {
        "directory": _service().directory_stats(),
        "charts": _service().charts(),
        **dashboard_metadata("filesystem+sqlite", quality="good"),
    }


@router.get("/reports/{rid}/preview", response_model=ReportPreviewResponse)
async def preview(rid: str):
    return _service().preview(rid)


@router.get("/reports/{rid}/related-data", response_model=ObjectResponse)
async def related_data(rid: str):
    return _service().related_data(rid)


@router.get("/reports/{rid}/file")
async def report_file(
    rid: str,
    principal: Principal = Depends(require_role(Role.VIEWER)),
):
    row = _service().report_row(rid)
    path = row["_path"]
    record_operator_action(state, principal, "download_report_file", rid, {"file_name": path.name}, trace_id=get_trace_id())
    media = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".json": "application/json",
        ".csv": "text/csv",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, filename=path.name, media_type=media, headers={"X-Trace-Id": get_trace_id()})


@router.post("/reports/{rid}/export-word", response_model=ActionResponse)
async def export_word(
    rid: str,
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    details = _service().export_target(rid, "docx")
    record_operator_action(state, principal, "export_report_word", rid, details, trace_id=get_trace_id())
    return _action("Word 报告已准备下载", details)


@router.post("/reports/{rid}/export-pdf", response_model=ActionResponse)
async def export_pdf(
    rid: str,
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    details = _service().export_target(rid, "pdf")
    record_operator_action(state, principal, "export_report_pdf", rid, details, trace_id=get_trace_id())
    return _action("PDF 报告已准备下载", details)


@router.post("/reports/{rid}/regenerate", response_model=ActionResponse)
async def regenerate(
    rid: str,
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    generated = _service().regenerate(rid)
    details = {
        "report_id": generated["id"],
        "database_ids": generated["database_ids"],
        "statuses": generated["statuses"],
        "errors": generated["errors"],
        "hashes": generated["hashes"],
    }
    record_operator_action(state, principal, "regenerate_report", rid, details, trace_id=get_trace_id())
    return _action("报告已重新生成", details)


@router.post("/reports/{rid}/print", response_model=ActionResponse)
async def print_report(
    rid: str,
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    job = _service().create_print_job(rid, principal.username)
    record_operator_action(state, principal, "queue_report_print", rid, job, trace_id=get_trace_id())
    return _action("打印任务已进入持久化队列", job)


@router.get("/reports/print-jobs/{job_id}", response_model=ObjectResponse)
async def print_job(job_id: str, _principal: Principal = Depends(require_role(Role.VIEWER))):
    return {"job": _service().print_job(job_id), **dashboard_metadata("sqlite", quality="good")}


@router.delete("/reports/{rid}", response_model=ActionResponse)
async def delete(
    rid: str,
    principal: Principal = Depends(require_role(Role.ADMIN)),
):
    details = _service().delete(rid)
    record_operator_action(state, principal, "delete_report", rid, details, trace_id=get_trace_id())
    return _action("报告已删除", details)
