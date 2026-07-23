from __future__ import annotations
import hmac
import ipaddress
import os
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router as api_router
from app.control.intent_service import ControlIntentPersistenceError
from app.api.errors import (
    TRACE_ID,
    http_exception_handler,
    new_trace_id,
    safety_persistence_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.services.lifecycle import shutdown, startup
from app.websocket.endpoint import router as ws_router
from app.services.app_state import state
from app.services.audit import AuditPersistenceError
from app.sidecar_runtime import request_shutdown

configure_logging()


def allowed_ui_origins() -> list[str]:
    configured = os.getenv(
        "CHASSIS_ALLOWED_UI_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    )
    origins: list[str] = []
    for raw in configured.split(","):
        origin = raw.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlsplit(origin)
        try:
            loopback = parsed.hostname == "localhost" or bool(parsed.hostname and ipaddress.ip_address(parsed.hostname).is_loopback)
            port = parsed.port
        except ValueError:
            loopback = False
            port = None
        if (
            parsed.scheme not in {"http", "https"}
            or not loopback
            or parsed.username is not None
            or parsed.password is not None
            or port is not None and not 1 <= port <= 65535
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError("CHASSIS_ALLOWED_UI_ORIGINS accepts only explicit localhost/loopback HTTP(S) origins")
        origins.append(origin)
    sidecar_token = os.getenv("CHASSIS_SIDECAR_TOKEN", "")
    if os.getenv("CHASSIS_ALLOW_FILE_ORIGIN", "") == "1":
        if len(sidecar_token) < 32:
            raise RuntimeError("file origin is allowed only behind a strong per-start sidecar credential")
        origins.append("null")
    if not origins:
        raise RuntimeError("CHASSIS_ALLOWED_UI_ORIGINS must contain at least one loopback origin")
    return origins


app = FastAPI(title="Chassis EOL Management Platform", version="1.0.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_ui_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-Id", "X-Chassis-Sidecar"],
)
app.include_router(api_router)
app.include_router(ws_router)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(AuditPersistenceError, safety_persistence_exception_handler)
app.add_exception_handler(ControlIntentPersistenceError, safety_persistence_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.middleware("http")
async def packaged_sidecar_boundary(request: Request, call_next):
    """Require the Electron process credential in packaged mode.

    The health probe intentionally exposes only a constant status and remains usable
    by local diagnostics. User authentication and role checks remain the authority
    behind this additional process boundary.
    """
    expected = os.getenv("CHASSIS_SIDECAR_TOKEN", "")
    if expected and request.method != "OPTIONS" and request.url.path != "/api/v1/health":
        supplied = request.headers.get("x-chassis-sidecar", "")
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse(
                status_code=403,
                content={
                    "code": "SIDECAR_CREDENTIAL_REQUIRED",
                    "message": "local desktop credential required",
                    "details": {},
                    "trace_id": getattr(request.state, "trace_id", ""),
                },
            )
    return await call_next(request)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = new_trace_id(request.headers.get("x-trace-id"))
    token = TRACE_ID.set(trace_id)
    request.state.trace_id = trace_id
    try:
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
    finally:
        TRACE_ID.reset(token)


@app.get("/internal/sidecar/readiness", include_in_schema=False)
async def readiness():
    ready = all((state.database, state.can, state.telemetry, state.storage_health))
    if not ready:
        raise HTTPException(status_code=503, detail={"code": "SIDECAR_NOT_READY", "message": "backend startup is incomplete"})
    scheduler_task = getattr(getattr(state, "tx_scheduler", None), "task", None)
    transmission_active = bool(scheduler_task and not scheduler_task.done())
    return {
        "status": "ready",
        "profile": state.config.profile,
        "vehicle_io": "mock-loopback" if state.config.profile != "production" else "production-not-connected",
        "control_transmission": "active" if transmission_active else "stopped",
    }


@app.post("/internal/sidecar/shutdown", include_in_schema=False)
async def sidecar_shutdown():
    if not os.getenv("CHASSIS_SIDECAR_TOKEN", ""):
        raise HTTPException(status_code=404, detail="not found")
    if not request_shutdown():
        raise HTTPException(status_code=503, detail={"code": "SIDECAR_SHUTDOWN_UNAVAILABLE", "message": "sidecar controller unavailable"})
    return {"status": "stopping"}

@app.on_event("startup")
async def on_startup():
    await startup()

@app.on_event("shutdown")
async def on_shutdown():
    await shutdown()
