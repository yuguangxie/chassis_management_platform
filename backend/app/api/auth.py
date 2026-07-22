from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.security.auth import AuthError, Principal, Role, auth_http_exception, require_role
from app.services.app_state import state


router = APIRouter(prefix="/auth", tags=["authentication"])


class AuthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CredentialRequest(AuthModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=128)


class BootstrapRequest(CredentialRequest):
    bootstrap_secret: str = Field(min_length=20, max_length=256)


class CreateAccountRequest(CredentialRequest):
    role: Role


class RevokeSessionRequest(AuthModel):
    reason: str = Field(min_length=2, max_length=200)


class BootstrapStatusResponse(AuthModel):
    required: bool
    method: str


class PrincipalResponse(AuthModel):
    username: str
    role: Role
    session_id: str
    expires_at: str | None
    permissions: list[str]


class SessionResponse(PrincipalResponse):
    token: str
    token_type: str = "Bearer"


class AccountResponse(AuthModel):
    username: str
    role: Role
    enabled: bool
    created_at: str


def _permissions(role: Role) -> list[str]:
    common = ["read_sensitive"]
    by_role = {
        Role.VIEWER: [],
        Role.OPERATOR: ["run_eol", "acknowledge_alarm", "export_data"],
        Role.ENGINEER: ["run_eol", "acknowledge_alarm", "export_data", "manual_control", "network_diagnostics", "edit_config", "reload_dbc"],
        Role.ADMIN: [
            "run_eol",
            "acknowledge_alarm",
            "export_data",
            "manual_control",
            "network_diagnostics",
            "edit_config",
            "reload_dbc",
            "apply_config_package",
            "manage_accounts",
            "maintenance",
            "delete_report",
        ],
    }
    return common + by_role[role]


def _principal_payload(principal: Principal) -> dict:
    return {
        "username": principal.username,
        "role": principal.role,
        "session_id": principal.session_id,
        "expires_at": principal.expires_at,
        "permissions": _permissions(principal.role),
    }


def _session_payload(principal: Principal, token: str) -> dict:
    return {**_principal_payload(principal), "token": token, "token_type": "Bearer"}


@router.get("/bootstrap/status", response_model=BootstrapStatusResponse)
async def bootstrap_status():
    return state.auth.bootstrap_status()


@router.post("/bootstrap", response_model=SessionResponse)
async def bootstrap(payload: BootstrapRequest):
    try:
        principal, token = state.auth.bootstrap_admin(payload.bootstrap_secret, payload.username, payload.password)
    except AuthError as exc:
        raise auth_http_exception(exc) from exc
    return _session_payload(principal, token)


@router.post("/login", response_model=SessionResponse)
async def login(payload: CredentialRequest):
    try:
        principal, token = state.auth.login(payload.username, payload.password)
    except AuthError as exc:
        raise auth_http_exception(exc) from exc
    return _session_payload(principal, token)


@router.post("/unlock", response_model=SessionResponse)
async def unlock(payload: CredentialRequest):
    try:
        principal, token = state.auth.unlock(payload.username, payload.password)
    except AuthError as exc:
        raise auth_http_exception(exc) from exc
    return _session_payload(principal, token)


@router.get("/me", response_model=PrincipalResponse)
async def me(principal: Principal = Depends(require_role(Role.VIEWER))):
    return _principal_payload(principal)


@router.post("/logout", status_code=204)
async def logout(principal: Principal = Depends(require_role(Role.VIEWER))):
    state.auth.logout(principal)
    return None


@router.post("/lock", status_code=204)
async def lock(principal: Principal = Depends(require_role(Role.VIEWER))):
    state.auth.lock(principal)
    return None


@router.post("/accounts", response_model=AccountResponse)
async def create_account(
    payload: CreateAccountRequest,
    principal: Principal = Depends(require_role(Role.ADMIN)),
):
    try:
        return state.auth.create_user(payload.username, payload.password, payload.role, principal)
    except AuthError as exc:
        raise auth_http_exception(exc) from exc


@router.get("/sessions")
async def sessions(
    username: str | None = None,
    _principal: Principal = Depends(require_role(Role.ADMIN)),
):
    return {"items": state.auth.list_sessions(username)}


@router.post("/sessions/{session_id}/revoke", status_code=204)
async def revoke_session(
    session_id: str,
    payload: RevokeSessionRequest,
    principal: Principal = Depends(require_role(Role.ADMIN)),
):
    try:
        state.auth.revoke(session_id, principal, payload.reason)
    except AuthError as exc:
        raise auth_http_exception(exc) from exc
    return None
