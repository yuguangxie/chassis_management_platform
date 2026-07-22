import os

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import allowed_ui_origins, app
from app.sidecar import _loopback_host


SIDECAR_TOKEN = "sidecar-test-credential-with-more-than-32-characters"


def test_file_origin_requires_strong_per_start_credential(monkeypatch):
    monkeypatch.setenv("CHASSIS_ALLOW_FILE_ORIGIN", "1")
    monkeypatch.delenv("CHASSIS_SIDECAR_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="per-start"):
        allowed_ui_origins()
    monkeypatch.setenv("CHASSIS_SIDECAR_TOKEN", SIDECAR_TOKEN)
    assert "null" in allowed_ui_origins()


def test_packaged_http_boundary_keeps_health_minimal_and_protects_data(monkeypatch, auth_headers):
    monkeypatch.setenv("CHASSIS_SIDECAR_TOKEN", SIDECAR_TOKEN)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        rejected = client.get("/api/v1/overview/summary", headers=auth_headers("viewer"))
        assert rejected.status_code == 403
        assert rejected.json()["code"] == "SIDECAR_CREDENTIAL_REQUIRED"
        accepted = client.get(
            "/api/v1/overview/summary",
            headers={**auth_headers("viewer"), "X-Chassis-Sidecar": SIDECAR_TOKEN},
        )
        assert accepted.status_code == 200
        ready = client.get(
            "/internal/sidecar/readiness",
            headers={"X-Chassis-Sidecar": SIDECAR_TOKEN},
        )
        assert ready.status_code == 200
        assert ready.json()["control_transmission"] == "stopped"


def test_packaged_websocket_rejects_missing_process_credential(monkeypatch):
    monkeypatch.setenv("CHASSIS_SIDECAR_TOKEN", SIDECAR_TOKEN)
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect(
                "/ws",
                subprotocols=["chassis-session", "chassis-token.test-viewer-token"],
            ):
                pass
        assert rejected.value.code == 4403


def test_sidecar_launcher_rejects_non_loopback_binding(monkeypatch):
    monkeypatch.setenv("CHASSIS_BACKEND_HOST", "0.0.0.0")
    with pytest.raises(RuntimeError, match="loopback"):
        _loopback_host()
    monkeypatch.setenv("CHASSIS_BACKEND_HOST", "127.0.0.1")
    assert _loopback_host() == "127.0.0.1"


def test_no_fixed_sidecar_secret_is_present_in_environment_example():
    example = (os.path.dirname(__file__) + "/../../.env.example")
    content = open(example, encoding="utf-8").read()
    assert "CHASSIS_SIDECAR_TOKEN=" not in content
