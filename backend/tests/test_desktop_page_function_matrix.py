from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import app


READ_CONTRACTS = [
    ("overview", "/api/v1/overview/summary", "recent_sessions"),
    ("network", "/api/v1/config/channels", "channels"),
    ("can-monitor", "/api/v1/can/frames/latest", "items"),
    ("signal-dashboard", "/api/v1/signals/dashboard", "watchlist"),
    ("realtime-curve", "/api/v1/signals/timeseries", "charts"),
    ("manual-control", "/api/v1/control/manual-feedback", "fields"),
    ("auto-test", "/api/v1/eol/dashboard", "steps"),
    ("alarm-diagnosis", "/api/v1/alarms/dashboard", "history"),
    ("report-management", "/api/v1/reports/dashboard", "reports"),
    ("history", "/api/v1/history/dashboard", "sessions"),
    ("system-settings", "/api/v1/config/system-dashboard", "storage"),
]


@pytest.mark.parametrize(("page", "path", "field"), READ_CONTRACTS)
def test_each_desktop_page_has_an_authenticated_successful_read(page, path, field, auth_headers):
    with TestClient(app) as client:
        unauthorized = client.get(path)
        assert unauthorized.status_code == 401, page
        response = client.get(path, headers=auth_headers("viewer"))
        assert response.status_code == 200, (page, response.text)
        assert field in response.json(), page


def test_each_desktop_page_major_write_is_real_role_checked_and_auditable(auth_headers):
    with TestClient(app) as client:
        operator = auth_headers("operator")
        engineer = auth_headers("engineer")
        admin = auth_headers("admin")

        writes = {
            "overview": client.post("/api/v1/reports/scan", json={}, headers=operator),
            "network": client.post("/api/v1/can/channels/self-test", json={}, headers=engineer),
            "can-monitor": client.post("/api/v1/can/frames/clear-display", json={}, headers=operator),
            "signal-dashboard": client.post("/api/v1/signals/dashboard-layout/reset", json={}, headers=operator),
            "realtime-curve": client.post("/api/v1/signals/snapshot", json={}, headers=operator),
            # This exercises the real motion endpoint while fail-closed feedback prevents a send.
            "manual-control": client.post(
                "/api/v1/control/121/send-once",
                json={"gear": "D", "drive_mode": "Remote", "target_speed": 1, "front_steer": 0, "rear_steer": 0, "brake_enable": False},
                headers=engineer,
            ),
            "auto-test": client.post(
                "/api/v1/eol/sessions",
                json={"chassis_no": "MOCK-UI-MATRIX", "vin": "LMOCKUI000000001", "serial_no": "MOCK-SN", "station_id": "LOOPBACK", "plan_id": "default_chassis_eol_v1"},
                headers=operator,
            ),
            "alarm-diagnosis": client.post("/api/v1/alarms/current-summary/ack", json={}, headers=operator),
            "report-management": client.post("/api/v1/reports/scan", json={}, headers=operator),
            "history": client.post("/api/v1/history/export", json={}, headers=operator),
        }
        exported = client.get("/api/v1/config/export", headers=admin)
        assert exported.status_code == 200
        writes["system-settings"] = client.post(
            "/api/v1/config/import",
            json={"package": exported.json()["package"], "dry_run": True},
            headers=admin,
        )

        for page, response in writes.items():
            expected = {409} if page == "manual-control" else {200}
            assert response.status_code in expected, (page, response.status_code, response.text)
            if response.status_code == 200:
                payload = response.json()
                assert payload.get("stub") is not True, page

        assert client.post("/api/v1/can/channels/self-test", json={}, headers=auth_headers("viewer")).status_code == 403
        assert client.post("/api/v1/config/import", json={}, headers=engineer).status_code == 403


def test_manual_feedback_exposes_presence_age_quality_channel_range_and_blocking(auth_headers):
    with TestClient(app) as client:
        response = client.get("/api/v1/control/manual-feedback", headers=auth_headers("engineer"))
        assert response.status_code == 200
        payload = response.json()
        assert payload["fields"]
        assert payload["stale"] is True
        required = {"rule", "label", "status", "present", "age_ms", "quality", "channel", "can_id", "value", "checks", "threshold", "blocking"}
        assert all(required <= item.keys() for item in payload["fields"])
        assert any(item["blocking"] and item["status"] in {"missing", "stale", "invalid", "out_of_range"} for item in payload["fields"])
