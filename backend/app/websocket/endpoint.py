import asyncio
import hmac
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .manager import manager
from .schemas import WsCommand
from app.services.app_state import state
from app.security.auth import ROLE_LEVEL, Role

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    offered = [item.strip() for item in ws.headers.get("sec-websocket-protocol", "").split(",") if item.strip()]
    expected_sidecar = os.getenv("CHASSIS_SIDECAR_TOKEN", "")
    if expected_sidecar:
        sidecar_protocol = next((item for item in offered if item.startswith("chassis-sidecar.")), "")
        supplied_sidecar = sidecar_protocol.removeprefix("chassis-sidecar.")
        if not hmac.compare_digest(supplied_sidecar, expected_sidecar):
            await ws.close(code=4403, reason="local desktop credential required")
            return
    token_protocol = next((item for item in offered if item.startswith("chassis-token.")), "")
    token = token_protocol.removeprefix("chassis-token.")
    principal = state.auth.authenticate(token)
    if principal is None or ROLE_LEVEL[principal.role] < ROLE_LEVEL[Role.VIEWER]:
        await ws.close(code=4401, reason="authentication required")
        return
    await manager.connect(ws, subprotocol="chassis-session" if "chassis-session" in offered else None)
    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
            except TimeoutError:
                if state.auth.authenticate(token) is None:
                    manager.disconnect(ws)
                    await ws.close(code=4401, reason="session expired or revoked")
                    return
                continue
            cmd = WsCommand(**data)
            if cmd.action == "subscribe":
                await manager.subscribe(ws, cmd.topics)
            elif cmd.action == "unsubscribe":
                await manager.unsubscribe(ws, cmd.topics)
    except WebSocketDisconnect:
        manager.disconnect(ws)
