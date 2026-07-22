from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.reports.printing import VirtualPrintBackend
from app.services.app_state import state
from support import seed_dashboard_session


def test_storage_admin_matrix_backup_cleanup_and_real_stats(auth_headers):
    with TestClient(app) as client:
        viewer = auth_headers("viewer")
        engineer = auth_headers("engineer")
        admin = auth_headers("admin")
        stats = client.get("/api/v1/storage/stats", headers=viewer)
        assert stats.status_code == 200
        payload = stats.json()
        root = Path(payload["data_root"]).resolve()
        assert payload["schema_version"] == payload["latest_schema_version"] == 3
        assert payload["database_writable"] is True
        assert all(root == Path(path).resolve() or root in Path(path).resolve().parents for path in payload["paths"].values())
        assert client.get("/api/v1/storage/backups", headers=viewer).status_code == 403
        assert client.post("/api/v1/storage/backups", json={}, headers=engineer).status_code == 403
        backup = client.post("/api/v1/storage/backups", json={}, headers=admin)
        assert backup.status_code == 200, backup.text
        backup_id = backup.json()["backup_id"]
        validated = client.get(f"/api/v1/storage/backups/{backup_id}/validate", headers=admin)
        assert validated.status_code == 200 and validated.json()["valid"] is True

        preview_body = {"cutoff_utc": "2020-01-01T00:00:00Z"}
        assert client.post("/api/v1/storage/cleanup/preview", json=preview_body, headers=engineer).status_code == 403
        preview = client.post("/api/v1/storage/cleanup/preview", json=preview_body, headers=admin)
        assert preview.status_code == 200 and preview.json()["dry_run"] is True
        assert preview.json()["protected"]["operator_actions"] == "all protected"
        assert client.post("/api/v1/storage/cleanup", json=preview_body, headers=admin).status_code == 422


def test_print_api_requires_preview_and_tracks_virtual_spooler(auth_headers):
    with TestClient(app) as client:
        generated = seed_dashboard_session(state, "EOL-PRINT-API")
        report_id = next(item for item in generated["database_ids"] if item.endswith("-pdf"))
        operator = auth_headers("operator")
        viewer = auth_headers("viewer")
        assert client.get("/api/v1/reports/printers", headers=viewer).json()["backend"] == "virtual"
        capabilities = client.get("/api/v1/reports/capabilities", headers=viewer)
        assert capabilities.status_code == 200
        assert capabilities.json()["report"]["ready"] is True
        assert client.post(f"/api/v1/reports/{report_id}/print", json={"preview_confirmed": False}, headers=operator).status_code == 422
        submitted = client.post(
            f"/api/v1/reports/{report_id}/print",
            json={"preview_confirmed": True, "printer_name": "Virtual PDF Printer"},
            headers=operator,
        )
        assert submitted.status_code == 200
        job = submitted.json()["details"]
        assert job["status"] == "QUEUED" and job["report_hash"]
        backend = state.printing.backend
        assert isinstance(backend, VirtualPrintBackend)
        backend.set_status(job["spooler_job_id"], "FAILED", "injected virtual failure")
        failed = client.get(f"/api/v1/reports/print-jobs/{job['job_id']}", headers=viewer).json()["job"]
        assert failed["status"] == "FAILED"
        retried = client.post(f"/api/v1/reports/print-jobs/{job['job_id']}/retry", json={}, headers=operator)
        assert retried.status_code == 200 and retried.json()["job"]["attempts"] == 2
        cancelled = client.post(f"/api/v1/reports/print-jobs/{job['job_id']}/cancel", json={}, headers=operator)
        assert cancelled.status_code == 200 and cancelled.json()["job"]["status"] == "CANCELLED"
        audit = state.database.query(
            "SELECT action_type,result FROM operator_actions WHERE target=? ORDER BY id",
            (job["job_id"],),
        )
        assert {row["action_type"] for row in audit} >= {"print_queued", "print_submitted", "print_retried", "print_cancelled"}
