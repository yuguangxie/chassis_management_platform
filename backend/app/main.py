from __future__ import annotations
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router as api_router
from app.api.errors import (
    TRACE_ID,
    http_exception_handler,
    new_trace_id,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.services.lifecycle import shutdown, startup
from app.websocket.endpoint import router as ws_router

configure_logging()
app = FastAPI(title="Chassis EOL Management Platform", version="1.0.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-Id"],
)
app.include_router(api_router)
app.include_router(ws_router)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


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

@app.on_event("startup")
async def on_startup():
    await startup()

@app.on_event("shutdown")
async def on_shutdown():
    await shutdown()
