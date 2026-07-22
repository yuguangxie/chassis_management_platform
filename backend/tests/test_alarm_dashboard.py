from fastapi.testclient import TestClient

from app.main import app
from app.services.app_state import state


def test_alarm_dashboard_complete_and_unsigned_bitmap(auth_headers):
    with TestClient(app) as client:
        state.signals.current["Balance_symbol_cell16"] = {"value": 0x8001}
        response = client.get("/api/v1/alarms/dashboard", headers=auth_headers("viewer"))
        assert response.status_code == 200
        payload = response.json()
        assert payload["data_source"] == "runtime+sqlite"
        assert payload["mock"] is False
        assert len(payload["warning_matrix_0x77"]) == 9
        assert len(payload["bms_protect_0x102"]["items"]) == 8
        assert payload["bms_protect_0x102"]["bitmap_bits"] == [1] + [0] * 14 + [1]
        assert payload["bms_protect_0x102"]["bit_order"] == "High -> Low"


def test_alarm_actions_use_real_resources_and_contract(auth_headers):
    with TestClient(app) as client:
        missing = client.post(
            "/api/v1/alarms/ALM-NOT-FOUND/ack",
            json={},
            headers=auth_headers("operator"),
        )
        assert missing.status_code == 404
        assert missing.json()["code"] == "ALARM_NOT_FOUND"
        assert missing.json()["trace_id"]

        exported = client.post(
            "/api/v1/alarms/export-diagnosis",
            json={},
            headers=auth_headers("operator"),
        )
        assert exported.status_code == 200
        assert exported.json()["mock"] is False
        assert exported.json()["details"]["download_url"]

        saved = client.put(
            "/api/v1/alarms/dashboard-layout",
            json={"layout": {"preset": "test"}},
            headers=auth_headers("engineer"),
        )
        assert saved.status_code == 200
        assert saved.json()["details"]["layout"] == {"preset": "test"}
