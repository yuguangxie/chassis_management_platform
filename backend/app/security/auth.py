from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import hmac
import logging
import os
from pathlib import Path
import secrets
from typing import Any
import uuid

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.paths import DATA_DIR
from app.core.time import utc_now


LOGGER = logging.getLogger(__name__)


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
    session_id: str = ""
    expires_at: str | None = None


class AuthError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 401, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuthService:
    """Local account and short-session authority for a single industrial workstation.

    Session secrets are returned once and only SHA-256 digests are stored. Passwords use
    scrypt with per-account salts. The optional in-memory token hook exists solely for
    isolated automated tests and is never populated from a build-time frontend value.
    """

    def __init__(self, profile: str, database: Any | None = None, bootstrap_path: Path | None = None) -> None:
        self.profile = profile
        self.database = database
        self.bootstrap_path = bootstrap_path or (DATA_DIR / "auth" / "bootstrap-admin.secret")
        self._test_tokens: dict[str, Principal] = {}
        self.session_ttl_seconds = self._bounded_env_int("CHASSIS_SESSION_TTL_SECONDS", 900, 60, 28_800)
        self.max_failed_attempts = self._bounded_env_int("CHASSIS_AUTH_MAX_FAILED_ATTEMPTS", 5, 3, 20)
        self.lockout_seconds = self._bounded_env_int("CHASSIS_AUTH_LOCKOUT_SECONDS", 300, 30, 86_400)
        self._dummy_salt = bytes.fromhex("de938fc51c59032816f59be1ef468ed5")

    @staticmethod
    def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer") from exc
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
        return value

    def bind_database(self, database: Any) -> None:
        self.database = database
        self.initialize_bootstrap()

    def initialize_bootstrap(self) -> None:
        if self.database is None:
            return
        if self.account_count() > 0:
            self.bootstrap_path.unlink(missing_ok=True)
            return
        environment_secret = os.getenv("CHASSIS_BOOTSTRAP_SECRET", "")
        if environment_secret:
            if len(environment_secret) < 20:
                raise RuntimeError("CHASSIS_BOOTSTRAP_SECRET must contain at least 20 characters")
            return
        self.bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.bootstrap_path.exists():
            secret = secrets.token_urlsafe(32)
            descriptor = os.open(self.bootstrap_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(secret)
            try:
                os.chmod(self.bootstrap_path, 0o600)
            except OSError:
                LOGGER.warning("Unable to tighten bootstrap file mode; protect the local data directory with OS ACLs")
        LOGGER.warning("Administrator bootstrap is required; retrieve the one-time secret from %s", self.bootstrap_path)

    def bootstrap_status(self) -> dict[str, Any]:
        required = self.account_count() == 0
        method = "disabled"
        if required:
            method = "environment" if os.getenv("CHASSIS_BOOTSTRAP_SECRET") else "local_file"
        return {"required": required, "method": method}

    def account_count(self) -> int:
        if self.database is None:
            return 0
        row = self.database.query_one("SELECT COUNT(*) AS count FROM auth_accounts")
        return int(row["count"] if row else 0)

    def bootstrap_admin(self, secret: str, username: str, password: str) -> tuple[Principal, str]:
        self._require_database()
        if self.account_count() != 0:
            self._audit(username, "auth_bootstrap_rejected", "auth.bootstrap", "ALREADY_INITIALIZED")
            raise AuthError("BOOTSTRAP_ALREADY_COMPLETED", "首次管理员初始化已经完成", status_code=409)
        expected = os.getenv("CHASSIS_BOOTSTRAP_SECRET", "")
        if not expected and self.bootstrap_path.exists():
            expected = self.bootstrap_path.read_text(encoding="utf-8").strip()
        if not expected or not hmac.compare_digest(secret, expected):
            self._audit(username, "auth_bootstrap_failed", "auth.bootstrap", "INVALID_SECRET")
            raise AuthError("INVALID_BOOTSTRAP_SECRET", "一次性初始化凭据无效", status_code=401)
        normalized = self._normalize_username(username)
        self._validate_password(password)
        self._insert_account(normalized, password, Role.ADMIN, "bootstrap")
        self.bootstrap_path.unlink(missing_ok=True)
        principal, token = self._issue_session(normalized, Role.ADMIN)
        self._audit(normalized, "auth_bootstrap_completed", "auth.bootstrap", "OK", Role.ADMIN)
        return principal, token

    def create_user(self, username: str, password: str, role: Role, created_by: Principal) -> dict[str, Any]:
        self._require_database()
        normalized = self._normalize_username(username)
        self._validate_password(password)
        if self.database.query_one("SELECT username FROM auth_accounts WHERE username=?", (normalized,)):
            raise AuthError("ACCOUNT_EXISTS", "账户已存在", status_code=409, details={"username": normalized})
        self._insert_account(normalized, password, role, created_by.username)
        self._audit(created_by.username, "auth_account_created", normalized, "OK", created_by.role, {"role": role.value})
        return {"username": normalized, "role": role.value, "enabled": True, "created_at": utc_now()}

    def login(self, username: str, password: str) -> tuple[Principal, str]:
        self._require_database()
        normalized = self._normalize_username(username)
        row = self.database.query_one("SELECT * FROM auth_accounts WHERE username=?", (normalized,))
        if row is None:
            self._password_digest(password, self._dummy_salt)
            self._audit(normalized, "auth_login_failed", "auth.session", "INVALID_CREDENTIALS")
            raise AuthError("INVALID_CREDENTIALS", "用户名或密码错误", status_code=401)
        if not bool(row["enabled"]):
            self._audit(normalized, "auth_login_failed", "auth.session", "ACCOUNT_DISABLED")
            raise AuthError("ACCOUNT_DISABLED", "账户已禁用", status_code=403)
        locked_until = self._parse_time(row.get("locked_until"))
        now = datetime.now(timezone.utc)
        if locked_until and locked_until > now:
            self._audit(normalized, "auth_login_blocked", "auth.session", "ACCOUNT_LOCKED")
            raise AuthError(
                "ACCOUNT_LOCKED",
                "登录失败次数过多，账户暂时锁定",
                status_code=429,
                details={"locked_until": locked_until.isoformat()},
            )
        valid = self._verify_password(password, str(row["password_salt"]), str(row["password_hash"]))
        if not valid:
            attempts = int(row.get("failed_attempts") or 0) + 1
            new_locked_until = None
            if attempts >= self.max_failed_attempts:
                new_locked_until = (now + timedelta(seconds=self.lockout_seconds)).isoformat()
                attempts = 0
            self.database.execute(
                "UPDATE auth_accounts SET failed_attempts=?,locked_until=?,updated_at=? WHERE username=?",
                (attempts, new_locked_until, utc_now(), normalized),
            )
            result = "ACCOUNT_LOCKED" if new_locked_until else "INVALID_CREDENTIALS"
            self._audit(normalized, "auth_login_failed", "auth.session", result)
            if new_locked_until:
                raise AuthError(
                    "ACCOUNT_LOCKED",
                    "登录失败次数过多，账户暂时锁定",
                    status_code=429,
                    details={"locked_until": new_locked_until},
                )
            raise AuthError(
                "INVALID_CREDENTIALS",
                "用户名或密码错误",
                status_code=401,
                details={"remaining_attempts": self.max_failed_attempts - attempts},
            )
        self.database.execute(
            "UPDATE auth_accounts SET failed_attempts=0,locked_until=NULL,updated_at=? WHERE username=?",
            (utc_now(), normalized),
        )
        principal, token = self._issue_session(normalized, Role(str(row["role"])))
        self._audit(normalized, "auth_login_succeeded", principal.session_id, "OK", principal.role)
        return principal, token

    def unlock(self, username: str, password: str) -> tuple[Principal, str]:
        principal, token = self.login(username, password)
        self.database.execute(
            "UPDATE auth_sessions SET status='REVOKED',revoked_at=?,revoke_reason='unlock replacement' "
            "WHERE account_username=? AND status='LOCKED'",
            (utc_now(), principal.username),
        )
        self._audit(principal.username, "auth_session_unlocked", principal.session_id, "OK", principal.role)
        return principal, token

    def logout(self, principal: Principal) -> None:
        self._set_session_status(principal.session_id, "REVOKED", "user logout")
        self._audit(principal.username, "auth_logout", principal.session_id, "OK", principal.role)

    def lock(self, principal: Principal) -> None:
        self._set_session_status(principal.session_id, "LOCKED", "workstation locked")
        self._audit(principal.username, "auth_session_locked", principal.session_id, "OK", principal.role)

    def revoke(self, session_id: str, principal: Principal, reason: str) -> None:
        row = self.database.query_one("SELECT id FROM auth_sessions WHERE id=?", (session_id,)) if self.database else None
        if row is None:
            raise AuthError("SESSION_NOT_FOUND", "会话不存在", status_code=404)
        self._set_session_status(session_id, "REVOKED", reason)
        self._audit(principal.username, "auth_session_revoked", session_id, "OK", principal.role, {"reason": reason})

    def install_token(self, token: str, username: str, role: Role | str) -> None:
        if self.profile != "test":
            raise RuntimeError("in-memory tokens are restricted to the test profile")
        self._test_tokens[token] = Principal(username=username, role=Role(role), session_id=f"test:{username}")

    def authenticate(self, token: str) -> Principal | None:
        principal, _reason = self.authenticate_with_reason(token)
        return principal

    def authenticate_with_reason(self, token: str) -> tuple[Principal | None, str]:
        if not token:
            return None, "AUTH_REQUIRED"
        for expected, principal in self._test_tokens.items():
            if hmac.compare_digest(token, expected):
                return principal, "OK"
        if self.database is None:
            return None, "INVALID_TOKEN"
        token_hash = self._token_hash(token)
        row = self.database.query_one(
            "SELECT s.*,a.role,a.enabled FROM auth_sessions s JOIN auth_accounts a ON a.username=s.account_username "
            "WHERE s.token_hash=?",
            (token_hash,),
        )
        if row is None:
            return None, "INVALID_TOKEN"
        status = str(row["status"])
        if status == "LOCKED":
            return None, "SESSION_LOCKED"
        if status != "ACTIVE":
            return None, "SESSION_REVOKED" if status == "REVOKED" else "SESSION_EXPIRED"
        expires = self._parse_time(str(row["expires_at"]))
        if expires is None or expires <= datetime.now(timezone.utc):
            self.database.execute(
                "UPDATE auth_sessions SET status='EXPIRED',revoked_at=?,revoke_reason='absolute expiry' WHERE id=?",
                (utc_now(), row["id"]),
            )
            return None, "SESSION_EXPIRED"
        if not bool(row["enabled"]):
            return None, "ACCOUNT_DISABLED"
        self.database.execute("UPDATE auth_sessions SET last_seen_at=? WHERE id=?", (utc_now(), row["id"]))
        return Principal(str(row["account_username"]), Role(str(row["role"])), str(row["id"]), expires.isoformat()), "OK"

    def list_sessions(self, username: str | None = None) -> list[dict[str, Any]]:
        self._require_database()
        sql = "SELECT id,account_username,status,issued_at,expires_at,last_seen_at,revoked_at,revoke_reason FROM auth_sessions"
        params: tuple[Any, ...] = ()
        if username:
            sql += " WHERE account_username=?"
            params = (self._normalize_username(username),)
        sql += " ORDER BY issued_at DESC LIMIT 200"
        return self.database.query(sql, params)

    def _insert_account(self, username: str, password: str, role: Role, created_by: str) -> None:
        salt = secrets.token_bytes(16)
        digest = self._password_digest(password, salt).hex()
        timestamp = utc_now()
        self.database.execute(
            "INSERT INTO auth_accounts(username,password_salt,password_hash,role,enabled,failed_attempts,created_at,created_by,updated_at) "
            "VALUES (?,?,?,?,1,0,?,?,?)",
            (username, salt.hex(), digest, role.value, timestamp, created_by, timestamp),
        )

    def _issue_session(self, username: str, role: Role) -> tuple[Principal, str]:
        token = secrets.token_urlsafe(32)
        session_id = str(uuid.uuid4())
        issued = datetime.now(timezone.utc)
        expires = issued + timedelta(seconds=self.session_ttl_seconds)
        self.database.execute(
            "INSERT INTO auth_sessions(id,account_username,token_hash,status,issued_at,expires_at,last_seen_at) VALUES (?,?,?,?,?,?,?)",
            (session_id, username, self._token_hash(token), "ACTIVE", issued.isoformat(), expires.isoformat(), issued.isoformat()),
        )
        return Principal(username, role, session_id, expires.isoformat()), token

    def _set_session_status(self, session_id: str, status: str, reason: str) -> None:
        if not session_id or session_id.startswith("test:"):
            return
        self._require_database()
        self.database.execute(
            "UPDATE auth_sessions SET status=?,revoked_at=?,revoke_reason=? WHERE id=?",
            (status, utc_now(), reason, session_id),
        )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _password_digest(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)

    def _verify_password(self, password: str, salt_hex: str, digest_hex: str) -> bool:
        try:
            actual = self._password_digest(password, bytes.fromhex(salt_hex)).hex()
        except ValueError:
            return False
        return hmac.compare_digest(actual, digest_hex)

    @staticmethod
    def _normalize_username(username: str) -> str:
        value = username.strip().lower()
        if not 3 <= len(value) <= 64 or not all(char.isalnum() or char in "._-" for char in value):
            raise AuthError("INVALID_USERNAME", "用户名必须为 3..64 位字母、数字、点、下划线或连字符", status_code=422)
        return value

    @staticmethod
    def _validate_password(password: str) -> None:
        if not 12 <= len(password) <= 128:
            raise AuthError("WEAK_PASSWORD", "密码长度必须为 12..128 位", status_code=422)
        classes = [any(char.islower() for char in password), any(char.isupper() for char in password), any(char.isdigit() for char in password), any(not char.isalnum() for char in password)]
        if sum(classes) < 3:
            raise AuthError("WEAK_PASSWORD", "密码必须至少包含大小写字母、数字、符号中的三类", status_code=422)

    @staticmethod
    def _parse_time(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def _audit(
        self,
        username: str,
        action: str,
        target: str,
        result: str,
        role: Role = Role.VIEWER,
        request: dict[str, Any] | None = None,
    ) -> None:
        if self.database is None:
            return
        import json

        try:
            self.database.execute(
                "INSERT INTO operator_actions(timestamp_utc,operator,role,action_type,target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?)",
                (utc_now(), username or "unknown", role.value, action, target, json.dumps(request or {}, ensure_ascii=False), result, ""),
            )
        except Exception:
            LOGGER.exception("failed to persist authentication audit event %s", action)

    def _require_database(self) -> None:
        if self.database is None:
            raise RuntimeError("authentication database is not initialized")


bearer = HTTPBearer(auto_error=False)


def auth_http_exception(error: AuthError) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message, "details": error.details},
        headers=headers,
    )


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
    principal, reason = state.auth.authenticate_with_reason(credentials.credentials)
    if principal is None:
        messages = {
            "SESSION_EXPIRED": "会话已过期，请重新登录",
            "SESSION_REVOKED": "会话已撤销，请重新登录",
            "SESSION_LOCKED": "工作站已锁定",
            "ACCOUNT_DISABLED": "账户已禁用",
        }
        raise HTTPException(
            status_code=401,
            detail={"code": reason, "message": messages.get(reason, "身份令牌无效"), "details": {}},
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

    dependency.minimum_role = minimum  # type: ignore[attr-defined]
    return dependency
