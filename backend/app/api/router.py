from fastapi import APIRouter, Depends

from app.security.auth import Role, require_role

from . import alarms, auth, can, config, control, dbc, eol, history, overview, reports, signals, storage

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(overview.router)
for module in (config, storage, can, dbc, signals, control, eol, alarms, reports, history):
    router.include_router(module.router, dependencies=[Depends(require_role(Role.VIEWER))])
