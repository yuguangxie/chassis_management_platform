import pytest
from fastapi.testclient import TestClient

from app.main import allowed_ui_origins, app


def test_default_cors_allows_only_declared_loopback_origins(monkeypatch):
    monkeypatch.delenv("CHASSIS_ALLOWED_UI_ORIGINS", raising=False)
    assert allowed_ui_origins() == ["http://127.0.0.1:5173", "http://localhost:5173"]
    with TestClient(app) as client:
        allowed = client.options(
            "/api/v1/auth/login",
            headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST"},
        )
        assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
        denied = client.options(
            "/api/v1/auth/login",
            headers={"Origin": "https://example.invalid", "Access-Control-Request-Method": "POST"},
        )
        assert "access-control-allow-origin" not in denied.headers


def test_cors_configuration_rejects_non_loopback_origin(monkeypatch):
    monkeypatch.setenv("CHASSIS_ALLOWED_UI_ORIGINS", "http://192.0.2.10:5173")
    with pytest.raises(RuntimeError, match="loopback"):
        allowed_ui_origins()


@pytest.mark.parametrize(
    "origin",
    [
        "http://operator@localhost:5173",
        "http://localhost:not-a-port",
        "file://localhost/app",
        "http://localhost:5173/path",
    ],
)
def test_cors_configuration_rejects_non_origin_syntax(monkeypatch, origin):
    monkeypatch.setenv("CHASSIS_ALLOWED_UI_ORIGINS", origin)
    with pytest.raises(RuntimeError, match="loopback"):
        allowed_ui_origins()
