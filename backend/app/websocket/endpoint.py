from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .manager import manager
from .schemas import WsCommand
from app.services.app_state import state
from app.security.auth import ROLE_LEVEL, Role

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    principal = state.auth.authenticate(ws.query_params.get("token", ""))
    if principal is None or ROLE_LEVEL[principal.role] < ROLE_LEVEL[Role.VIEWER]:
        await ws.close(code=4401, reason="authentication required")
        return
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            cmd = WsCommand(**data)
            if cmd.action == "subscribe":
                await manager.subscribe(ws, cmd.topics)
            elif cmd.action == "unsubscribe":
                await manager.unsubscribe(ws, cmd.topics)
    except WebSocketDisconnect:
        manager.disconnect(ws)
