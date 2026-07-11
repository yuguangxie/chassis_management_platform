from fastapi import APIRouter, Depends, HTTPException

from app.core.time import utc_now
from app.services.app_state import state
from app.security.auth import Principal, Role, require_role
from app.services.audit import record_operator_action

router = APIRouter()


def _display_time() -> str:
    return utc_now().replace("T", " ")[:19]


@router.get("/dbc/status")
async def status(_principal: Principal = Depends(require_role(Role.VIEWER))):
    raw = state.dbc.status()
    messages = state.dbc.messages()
    return {
        **raw,
        "status": "loaded" if raw.get("loaded") else "raw-only" if raw.get("raw_only") else "failed",
        "message_count": len(messages),
        "signal_count": sum(len(item.get("signals", [])) for item in messages),
        "hash": str(raw.get("hash") or "")[:12],
        "loaded_at": _display_time(),
    }


@router.post("/dbc/reload")
async def reload(principal: Principal = Depends(require_role(Role.ENGINEER))):
    raw = state.dbc.reload()
    messages = state.dbc.messages()
    response = {
        "ok": bool(raw.get("loaded") or raw.get("raw_only")),
        **raw,
        "status": "loaded" if raw.get("loaded") else "raw-only" if raw.get("raw_only") else "failed",
        "message_count": len(messages),
        "signal_count": sum(len(item.get("signals", [])) for item in messages),
        "hash": str(raw.get("hash") or "")[:12],
        "loaded_at": _display_time(),
        "message": "DBC 已重新扫描并加载" if raw.get("loaded") else "DBC 未加载，当前保持 raw-only 模式",
    }
    record_operator_action(state, principal, "reload_dbc", raw.get("file") or "assets/*.dbc", raw)
    ws = getattr(state, "ws", None)
    if ws is not None:
        await ws.broadcast("dbc.status_changed", response)
    return response


@router.get("/dbc/messages")
async def messages(_principal: Principal = Depends(require_role(Role.VIEWER))):
    return state.dbc.messages()


@router.get("/dbc/messages/{can_id}")
async def message(can_id: str, _principal: Principal = Depends(require_role(Role.VIEWER))):
    cid = int(can_id, 16) if can_id.lower().startswith("0x") else int(can_id)
    msg = state.dbc.message(cid)
    if not msg:
        raise HTTPException(404, "message not found")
    return msg
