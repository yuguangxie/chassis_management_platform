from fastapi.testclient import TestClient

from app.main import app


def test_only_minimal_health_and_auth_entrypoints_are_public():
    public_paths = {
        "/api/v1/health",
        "/api/v1/auth/bootstrap/status",
        "/api/v1/auth/bootstrap",
        "/api/v1/auth/login",
        "/api/v1/auth/unlock",
    }
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/v1") or path in public_paths:
            continue
        dependency_calls = {
            getattr(dependency.call, "__name__", "")
            for dependency in getattr(route, "dependant", ()).dependencies
        }
        assert "dependency" in dependency_calls, f"sensitive route has no role dependency: {path}"

    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        for path in (
            "/api/v1/overview/summary",
            "/api/v1/signals/current",
            "/api/v1/can/channels/status",
            "/api/v1/alarms/current",
            "/api/v1/reports/dashboard",
        ):
            assert client.get(path).status_code == 401, path


def test_operator_engineer_admin_api_matrix(auth_headers):
    with TestClient(app) as client:
        assert client.get("/api/v1/overview/summary", headers=auth_headers("operator")).status_code == 200
        assert client.post("/api/v1/control/121/preview", json={}, headers=auth_headers("operator")).status_code == 403
        assert client.post("/api/v1/control/121/preview", json={}, headers=auth_headers("engineer")).status_code != 403
        assert client.put(
            "/api/v1/config/channels",
            json={"channels": []},
            headers=auth_headers("engineer"),
        ).status_code == 403
        assert client.get("/api/v1/audit/operator-actions", headers=auth_headers("admin")).status_code == 200
