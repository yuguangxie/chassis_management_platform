from fastapi.testclient import TestClient

from app.main import app
from app.services.app_state import state
from support import seed_dashboard_session


def test_default_identity_is_not_admin():
    assert state.current_role != "admin"
    assert state.auth.authenticate("legacy-static-token") is None


def test_unauthenticated_and_viewer_control_requests_fail(auth_headers):
    payload = {"gear": "D", "target_speed": 1.0}
    with TestClient(app) as client:
        seed_dashboard_session(state)
        assert client.post("/api/v1/control/121/preview", json=payload).status_code == 401
        assert client.post("/api/v1/control/121/preview", json=payload, headers=auth_headers("viewer")).status_code == 403


def test_forged_body_role_cannot_enter_maintenance(auth_headers):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/maintenance/enter",
            json={"confirmation": "MAINTENANCE", "reason": "forged", "role": "admin"},
            headers=auth_headers("engineer"),
        )
        assert response.status_code == 403
        assert response.json()["code"] == "INSUFFICIENT_ROLE"
        assert response.json()["trace_id"]


def test_unauthenticated_report_delete_and_forged_header_fail(auth_headers):
    with TestClient(app) as client:
        seed_dashboard_session(state)
        report_id = client.get("/api/v1/reports/dashboard", headers=auth_headers("viewer")).json()["selected_report"]["report_id"]
        assert client.delete(f"/api/v1/reports/{report_id}").status_code == 401
        response = client.delete(
            f"/api/v1/reports/{report_id}",
            headers={**auth_headers("operator"), "x-role": "admin"},
        )
        assert response.status_code == 403
