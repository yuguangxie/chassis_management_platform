from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.app_state import state
from support import seed_dashboard_session


def test_report_dashboard_uses_sqlite_and_filesystem(auth_headers):
    with TestClient(app) as client:
        seed_dashboard_session(state)
        response = client.get("/api/v1/reports/dashboard", headers=auth_headers("viewer"))
        assert response.status_code == 200
        payload = response.json()
        assert payload["data_source"] == "sqlite+filesystem"
        assert payload["mock"] is False
        assert Path(payload["directory"]["path"]).is_dir()
        assert payload["reports"]
        selected = payload["selected_report"]
        assert selected["file_sha256"]
        assert selected["file_size_bytes"] > 0
        assert selected["preview"]["total_pages"] >= 1
        if selected["file_type"] == "pdf":
            assert selected["preview_image_data_url"].startswith("data:image/png;base64,")


def test_report_operations_require_identity_and_return_real_jobs(auth_headers):
    with TestClient(app) as client:
        seed_dashboard_session(state)
        viewer = auth_headers("viewer")
        dashboard = client.get("/api/v1/reports/dashboard", headers=viewer).json()
        report_id = dashboard["selected_report"]["report_id"]
        operator = auth_headers("operator")
        assert client.post("/api/v1/reports/scan", json={}, headers=operator).status_code == 200
        opened = client.post("/api/v1/reports/open-directory", json={}, headers=operator)
        assert opened.status_code == 200
        assert Path(opened.json()["details"]["path"]).is_dir()
        assert client.get(f"/api/v1/reports/{report_id}/preview", headers=viewer).status_code == 200
        assert client.get(f"/api/v1/reports/{report_id}/related-data", headers=viewer).status_code == 200
        word = client.post(f"/api/v1/reports/{report_id}/export-word", json={}, headers=operator)
        pdf = client.post(f"/api/v1/reports/{report_id}/export-pdf", json={}, headers=operator)
        assert word.status_code == pdf.status_code == 200
        assert word.json()["details"]["download_url"]
        assert pdf.json()["details"]["download_url"]
        printed = client.post(
            f"/api/v1/reports/{report_id}/print",
            json={"preview_confirmed": True},
            headers=operator,
        )
        assert printed.status_code == 200
        assert printed.json()["details"]["status"] == "QUEUED"

        denied = client.delete(f"/api/v1/reports/{report_id}", headers=operator)
        assert denied.status_code == 403
        assert denied.json()["code"] == "INSUFFICIENT_ROLE"
        forged = client.delete(f"/api/v1/reports/{report_id}", headers={**operator, "x-role": "admin"})
        assert forged.status_code == 403
