from __future__ import annotations

from contextvars import ContextVar
import re
import uuid
from typing import Any

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.control.intent_service import ControlIntentPersistenceError
from app.services.audit import AuditPersistenceError


TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="")
TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def new_trace_id(candidate: str | None = None) -> str:
    value = (candidate or "").strip()
    return value if TRACE_PATTERN.fullmatch(value) else uuid.uuid4().hex


def get_trace_id() -> str:
    return TRACE_ID.get() or uuid.uuid4().hex


def with_trace(payload: dict[str, Any]) -> dict[str, Any]:
    return {**payload, "trace_id": get_trace_id()}


def _error_payload(detail: Any, default_code: str, default_message: str) -> dict[str, Any]:
    if isinstance(detail, dict):
        nested = detail.get("error") if isinstance(detail.get("error"), dict) else detail
        return {
            "code": str(nested.get("code") or default_code),
            "message": str(nested.get("message") or default_message),
            "details": nested.get("details", {}),
            "trace_id": get_trace_id(),
        }
    return {
        "code": default_code,
        "message": str(detail or default_message),
        "details": {},
        "trace_id": get_trace_id(),
    }


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    payload = _error_payload(exc.detail, f"HTTP_{exc.status_code}", "请求失败")
    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
        headers={**(exc.headers or {}), "X-Trace-Id": payload["trace_id"]},
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    for error in errors:
        context = error.get("ctx")
        if isinstance(context, dict):
            error["ctx"] = {
                key: str(value) if isinstance(value, BaseException) else value
                for key, value in context.items()
            }
    payload = {
        "code": "VALIDATION_ERROR",
        "message": "请求参数校验失败",
        "details": {"errors": jsonable_encoder(errors)},
        "trace_id": get_trace_id(),
    }
    return JSONResponse(status_code=422, content=payload, headers={"X-Trace-Id": payload["trace_id"]})


async def safety_persistence_exception_handler(
    _request: Request,
    exc: AuditPersistenceError | ControlIntentPersistenceError,
) -> JSONResponse:
    payload = {
        "code": getattr(exc, "code", "SAFETY_PERSISTENCE_UNAVAILABLE"),
        "message": "安全操作记录不可写，已保持联锁拒绝",
        "details": {"blocking": True, "exception": type(exc).__name__},
        "trace_id": get_trace_id(),
    }
    return JSONResponse(status_code=503, content=payload, headers={"X-Trace-Id": payload["trace_id"]})


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    payload = {
        "code": "INTERNAL_ERROR",
        "message": "服务器内部错误",
        "details": {"exception": type(exc).__name__},
        "trace_id": get_trace_id(),
    }
    return JSONResponse(status_code=500, content=payload, headers={"X-Trace-Id": payload["trace_id"]})
