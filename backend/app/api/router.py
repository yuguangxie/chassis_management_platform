from fastapi import APIRouter

from . import alarms, can, config, control, dbc, eol, history, overview, reports, signals

router = APIRouter(prefix="/api/v1")
for module in (overview, config, can, dbc, signals, control, eol, alarms, reports, history):
    router.include_router(module.router)
