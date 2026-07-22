from fastapi.testclient import TestClient

from app.main import app


def test_network_diagnostics_use_socket_and_runtime_measurements(auth_headers):
    with TestClient(app) as client:
        assert client.post("/api/v1/can/channels/self-test", json={}, headers=auth_headers("viewer")).status_code == 403
        response = client.post("/api/v1/can/channels/self-test", json={}, headers=auth_headers("engineer"))
        assert response.status_code == 200
        payload = response.json()
        assert payload["data_source"] == "os-socket+runtime-statistics"
        assert payload["mock"] is False
        assert payload["ping_latency_ms"] is None
        assert payload["channels"]
        assert all(item["local_endpoint"].startswith("127.0.0.1:") for item in payload["channels"])
        assert all(item["bind_status"] in {"owned_by_runtime", "available"} for item in payload["channels"])
        assert all(item["source_allowlist_enforced"] for item in payload["channels"])
        assert all(item["tcp_state"] == "not_applicable" for item in payload["channels"])


def test_channel_summary_reports_measured_port_and_frame_state(auth_headers):
    with TestClient(app) as client:
        response = client.get("/api/v1/config/channels", headers=auth_headers("viewer"))
        assert response.status_code == 200
        payload = response.json()
        assert payload["local_network"]["diagnostic_source"] == "os-socket+runtime-statistics"
        assert payload["local_network"]["link_speed"] == "not-measured"
        assert all(item["status"] != "free" for item in payload["local_network"]["ports"])
        for channel in payload["channels"]:
            assert channel["bind_status"] in {"owned_by_runtime", "available"}
            assert channel["rx_status"] in {"unconfirmed", "receive_confirmed"}
            assert channel["source_allowlist_enforced"] is True
