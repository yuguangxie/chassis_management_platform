from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hmac
import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


class Role(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ENGINEER = "engineer"
    ADMIN = "admin"


ROLE_LEVEL = {
    Role.VIEWER: 10,
    Role.OPERATOR: 20,
    Role.ENGINEER: 30,
    Role.ADMIN: 40,
}


@dataclass(frozen=True)
class Principal:
    username: str
    role: Role


class AuthService:
    def __init__(self, profile: str) -> None:
        self.profile = profile
        self._tokens: dict[str, Principal] = {}
        self._load_environment_tokens()

    def _load_environment_tokens(self) -> None:
        for role in Role:
            token = os.getenv(f"CHASSIS_{role.value.upper()}_TOKEN")
            username = os.getenv(f"CHASSIS_{role.value.upper()}_USER", role.value)
            if token:
                self._tokens[token] = Principal(username=username, role=role)
        if self.profile in {"dev", "mock", "test"}:
            self._tokens.setdefault("dev-viewer-token", Principal("dev-viewer", Role.VIEWER))
            self._tokens.setdefault("dev-operator-token", Principal("dev-operator", Role.OPERATOR))
            self._tokens.setdefault("dev-engineer-token", Principal("dev-engineer", Role.ENGINEER))

    def install_token(self, token: str, username: str, role: Role | str) -> None:
        self._tokens[token] = Principal(username=username, role=Role(role))

    def authenticate(self, token: str) -> Principal | None:
        for expected, principal in self._tokens.items():
            if hmac.compare_digest(token, expected):
                return principal
        return None


bearer = HTTPBearer(auto_error=False)


async def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal:
    from app.services.app_state import state

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "需要可信身份认证", "details": {}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    principal = state.auth.authenticate(credentials.credentials)
    if principal is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "身份令牌无效", "details": {}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def require_role(minimum: Role):
    async def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if ROLE_LEVEL[principal.role] < ROLE_LEVEL[minimum]:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "INSUFFICIENT_ROLE",
                    "message": "当前身份权限不足",
                    "details": {"required": minimum.value, "actual": principal.role.value},
                },
            )
        return principal

    return dependency
