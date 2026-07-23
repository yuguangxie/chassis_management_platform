from fastapi.testclient import TestClient

from app.main import app


def test_eol_dashboard_has_no_fixed_running_mock(auth_headers):
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/eol/dashboard", headers=auth_headers("viewer")
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] in {"idle", "database_session"}
        assert not (
            payload["source"] == "idle"
            and payload["session"]["overall_status"] == "RUNNING"
        )
        assert payload["session"]["test_plan"] == "低速无人车线控底盘默认下线检测方案"


def test_eol_dashboard_tracks_created_actual_session(auth_headers):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/eol/sessions",
            headers=auth_headers("operator"),
            json={
                "chassis_no": "PH2-API",
                "vin": "L0000000000000002",
                "serial_no": "PH2-API-SN",
                "vehicle_series": "JD",
                "work_order_id": "PH2-API-WO",
                "plan_id": "default_chassis_eol_v1",
                "mock_session": True,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["id"]
        dashboard = client.get(
            "/api/v1/eol/dashboard", headers=auth_headers("viewer")
        ).json()
        assert dashboard["source"] == "actual_session"
        assert dashboard["session"]["session_id"] == session_id
        assert dashboard["session"]["overall_status"] == "WAIT"
        assert dashboard["steps"][0]["name"] == "上电自检"
        assert len(dashboard["steps"]) == 12
