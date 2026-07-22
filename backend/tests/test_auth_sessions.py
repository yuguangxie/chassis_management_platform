from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.security.auth import AuthError, AuthService, Role
from app.storage.database import Database


ADMIN_PASSWORD = "Initial-Admin-2026!"
OPERATOR_PASSWORD = "Operator-Access-2026!"


@pytest.fixture
def auth_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHASSIS_BOOTSTRAP_SECRET", "bootstrap-secret-used-only-by-this-test")
    database = Database(tmp_path / "identity.db")
    service = AuthService("test", database, tmp_path / "bootstrap.secret")
    service.initialize_bootstrap()
    yield service
    database.close()


def test_bootstrap_is_one_time_and_login_issues_short_session(auth_service: AuthService):
    status = auth_service.bootstrap_status()
    assert status == {"required": True, "method": "environment"}
    principal, token = auth_service.bootstrap_admin(
        "bootstrap-secret-used-only-by-this-test", "Plant.Admin", ADMIN_PASSWORD
    )
    assert principal.role is Role.ADMIN
    assert principal.expires_at
    assert auth_service.authenticate(token) == principal
    stored = auth_service.database.query_one("SELECT token_hash FROM auth_sessions WHERE id=?", (principal.session_id,))
    assert stored and stored["token_hash"] != token and len(stored["token_hash"]) == 64
    audits = auth_service.database.query("SELECT request_json FROM operator_actions WHERE action_type LIKE 'auth_%'")
    assert all(token not in row["request_json"] for row in audits)
    assert auth_service.bootstrap_status()["required"] is False
    with pytest.raises(AuthError) as error:
        auth_service.bootstrap_admin(
            "bootstrap-secret-used-only-by-this-test", "other.admin", ADMIN_PASSWORD
        )
    assert error.value.code == "BOOTSTRAP_ALREADY_COMPLETED"


def test_login_failure_limit_lock_and_later_success(auth_service: AuthService):
    admin, _ = auth_service.bootstrap_admin(
        "bootstrap-secret-used-only-by-this-test", "admin", ADMIN_PASSWORD
    )
    auth_service.create_user("operator01", OPERATOR_PASSWORD, Role.OPERATOR, admin)
    auth_service.max_failed_attempts = 3
    for _ in range(2):
        with pytest.raises(AuthError) as error:
            auth_service.login("operator01", "Wrong-Password-2026!")
        assert error.value.code == "INVALID_CREDENTIALS"
    with pytest.raises(AuthError) as error:
        auth_service.login("operator01", "Wrong-Password-2026!")
    assert error.value.code == "ACCOUNT_LOCKED"
    with pytest.raises(AuthError) as error:
        auth_service.login("operator01", OPERATOR_PASSWORD)
    assert error.value.code == "ACCOUNT_LOCKED"
    auth_service.database.execute(
        "UPDATE auth_accounts SET locked_until=? WHERE username='operator01'",
        ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),),
    )
    principal, token = auth_service.login("operator01", OPERATOR_PASSWORD)
    assert principal.role is Role.OPERATOR
    assert auth_service.authenticate(token) is not None


def test_lock_unlock_expiry_logout_and_admin_revocation(auth_service: AuthService):
    admin, _ = auth_service.bootstrap_admin(
        "bootstrap-secret-used-only-by-this-test", "admin", ADMIN_PASSWORD
    )
    auth_service.create_user("operator01", OPERATOR_PASSWORD, Role.OPERATOR, admin)

    operator, token = auth_service.login("operator01", OPERATOR_PASSWORD)
    auth_service.lock(operator)
    assert auth_service.authenticate_with_reason(token) == (None, "SESSION_LOCKED")
    unlocked, unlocked_token = auth_service.unlock("operator01", OPERATOR_PASSWORD)
    assert auth_service.authenticate(unlocked_token) == unlocked

    auth_service.database.execute(
        "UPDATE auth_sessions SET expires_at=? WHERE id=?",
        ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), unlocked.session_id),
    )
    assert auth_service.authenticate_with_reason(unlocked_token) == (None, "SESSION_EXPIRED")

    fresh, fresh_token = auth_service.login("operator01", OPERATOR_PASSWORD)
    auth_service.revoke(fresh.session_id, admin, "shift ended")
    assert auth_service.authenticate_with_reason(fresh_token) == (None, "SESSION_REVOKED")

    final, final_token = auth_service.login("operator01", OPERATOR_PASSWORD)
    auth_service.logout(final)
    assert auth_service.authenticate_with_reason(final_token) == (None, "SESSION_REVOKED")
