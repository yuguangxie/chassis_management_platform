from fastapi.testclient import TestClient

from app.main import app
from app.services.app_state import state
from support import seed_dashboard_session


def test_history_dashboard_real_pagination_filter_and_empty_result():
    with TestClient(app) as client:
        seed_dashboard_session(state)
        dashboard = client.get("/api/v1/history/dashboard", params={"page": 1, "page_size": 7})
        assert dashboard.status_code == 200
        payload = dashboard.json()
        assert payload["data_source"] == "sqlite+filesystem"
        assert payload["mock"] is False
        assert len(payload["sessions"]) <= 7
        assert payload["pagination"]["total"] == payload["summary"]["filtered_count"]

        empty = client.get("/api/v1/history/dashboard", params={"vin": "VIN-NOT-FOUND-EXACT"}).json()
        assert empty["sessions"] == []
        assert empty["selected_session"] is None
        assert empty["pagination"]["total"] == 0
        assert empty["pagination"]["total_pages"] == 0


def test_test_session_linked_resources_and_download_contract(auth_headers):
    with TestClient(app) as client:
        seed_dashboard_session(state)
        dashboard = client.get("/api/v1/history/dashboard", params={"page_size": 1}).json()
        assert dashboard["sessions"]
        session_id = dashboard["sessions"][0]["session_id"]
        detail = client.get(f"/api/v1/test-sessions/{session_id}")
        timeline = client.get(f"/api/v1/test-sessions/{session_id}/timeline")
        actions = client.get(f"/api/v1/test-sessions/{session_id}/operator-actions")
        downloads = client.get(f"/api/v1/test-sessions/{session_id}/downloads")
        assert detail.status_code == timeline.status_code == actions.status_code == downloads.status_code == 200
        assert isinstance(timeline.json(), list)
        assert len(downloads.json()) == 5

        invalid = client.get(
            f"/api/v1/test-sessions/{session_id}/download/not-supported",
            headers=auth_headers("viewer"),
        )
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "INVALID_FILE_TYPE"


def test_history_statistics_and_pareto_are_computed():
    with TestClient(app) as client:
        seed_dashboard_session(state)
        payload = client.get("/api/v1/history/statistics").json()
        assert payload["summary"]["total_tests"] >= payload["summary"]["fail_count"]
        assert 0 <= payload["summary"]["pass_rate"] <= 100
        pareto = payload["charts"]["failure_pareto"]
        assert len(pareto["counts"]) == len(pareto["cumulative_percent"])
        if pareto["counts"]:
            assert pareto["cumulative_percent"][-1] == 100.0
