from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.api import config as config_api
from app.main import app
from app.services.app_state import state


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config_api, "SYSTEM_SETTINGS_PATH", tmp_path / "system_settings.yaml")
    state.maintenance_mode = False
    state.current_role = "operator"
    state.mock_enabled = False
    state.maintenance_features = {
        "mock_can_gateway": False,
        "enable_0x123": False,
        "enable_0x126": False,
        "allow_canopen_nmt": False,
        "enable_pid_debug": False,
        "dual_control_channel_allowed": False,
    }


def test_system_dashboard_has_complete_structure(auth_headers):
    with TestClient(app) as client:
        response = client.get("/api/v1/config/system-dashboard", headers=auth_headers("viewer"))
        assert response.status_code == 200
        payload = response.json()
        assert payload["basic"]["station_id"] == "EOL-STATION-01"
        assert payload["basic"]["control_channel"] == "CAN2"
        assert len(payload["dbc"]["overrides"]) == 5
        assert len(payload["thresholds"]) >= 23
        assert len(payload["roles"]) == 4
        assert len(payload["config_history"]) >= 4
        assert payload["maintenance"]["enable_0x123"] is False
        assert payload["maintenance"]["enable_0x126"] is False
        assert payload["maintenance"]["allow_canopen_nmt"] is False


def test_save_normal_config_is_atomic_and_audited(auth_headers):
    with TestClient(app) as client:
        before = len(client.get("/api/v1/config/history", headers=auth_headers("viewer")).json())
        response = client.put(
            "/api/v1/config",
            json={
                "basic": {"language": "en-US"},
                "role": "engineer",
                "reason": "普通语言配置修改",
            },
            headers=auth_headers("engineer"),
        )
        assert response.status_code == 200
        assert response.json()["saved"] is True
        assert config_api.SYSTEM_SETTINGS_PATH.exists()
        dashboard = client.get("/api/v1/config/system-dashboard", headers=auth_headers("viewer")).json()
        assert dashboard["basic"]["language"] == "en-US"
        after = len(client.get("/api/v1/config/history", headers=auth_headers("viewer")).json())
        assert after >= before
        assert any(item["key"] == "basic.language" for item in client.get("/api/v1/config/history", headers=auth_headers("viewer")).json())


def test_out_of_range_threshold_is_rejected(auth_headers):
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/config",
            json={
                "thresholds": [
                    {
                        "key": "control_period_ms",
                        "label": "0x121 发送周期",
                        "value": 200,
                        "min": 10,
                        "max": 100,
                        "unit": "ms",
                        "scope": "control",
                        "description": "period",
                        "dangerous": False,
                    }
                ],
                "role": "engineer",
                "reason": "边界测试",
            },
            headers=auth_headers("engineer"),
        )
        assert response.status_code == 422
        assert response.json()["code"] == "THRESHOLD_OUT_OF_RANGE"


def test_non_admin_cannot_enter_maintenance_mode(auth_headers):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/maintenance/enter",
            json={"confirmation": "MAINTENANCE", "reason": "台架调试", "role": "admin"},
            headers=auth_headers("engineer"),
        )
        assert response.status_code == 403
        assert response.json()["code"] == "INSUFFICIENT_ROLE"


@pytest.mark.parametrize("feature", ["enable_0x123", "enable_0x126", "allow_canopen_nmt"])
def test_dangerous_feature_requires_maintenance_mode(feature: str, auth_headers):
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/maintenance/features",
            json={feature: True, "confirmation": "MAINTENANCE", "reason": "台架调试", "role": "engineer"},
            headers=auth_headers("admin"),
        )
        assert response.status_code == 409
        assert response.json()["code"] == "MAINTENANCE_MODE_REQUIRED"


def test_dual_control_channel_is_rejected(auth_headers):
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/config",
            json={"control_channels": ["CAN1", "CAN2"], "role": "viewer", "reason": "边界测试"},
            headers=auth_headers("admin"),
        )
        assert response.status_code == 409
        assert response.json()["code"] == "MULTIPLE_CONTROL_CHANNELS"


def test_0x126_angle_speed_range_is_validated(auth_headers):
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/maintenance/features",
            json={"steering_angle_speed_deg_s": 100, "confirmation": "MAINTENANCE", "reason": "台架调试", "role": "admin"},
            headers=auth_headers("admin"),
        )
        assert response.status_code == 422


def test_restore_safe_defaults_disables_all_dangerous_features(auth_headers):
    with TestClient(app) as client:
        state.maintenance_mode = True
        state.mock_enabled = True
        state.maintenance_features.update(
            {"mock_can_gateway": True, "enable_0x123": True, "enable_0x126": True, "allow_canopen_nmt": True, "enable_pid_debug": True}
        )
        response = client.post(
            "/api/v1/config/restore-safe-defaults",
            json={"confirmation": "RESTORE", "reason": "恢复安全默认", "role": "operator"},
            headers=auth_headers("admin"),
        )
        assert response.status_code == 200
        dashboard = client.get("/api/v1/config/system-dashboard", headers=auth_headers("viewer")).json()
        assert dashboard["maintenance"]["maintenance_mode"] is False
        assert dashboard["maintenance"]["mock_can_gateway"] is False
        assert dashboard["maintenance"]["enable_0x123"] is False
        assert dashboard["maintenance"]["enable_0x126"] is False
        assert dashboard["maintenance"]["allow_canopen_nmt"] is False
        assert dashboard["maintenance"]["dual_control_channel_allowed"] is False
        assert dashboard["basic"]["control_channel"] == "CAN2"


def test_dbc_reload_and_stub_operations_are_stable(auth_headers):
    with TestClient(app) as client:
        reload_response = client.post("/api/v1/dbc/reload", json={}, headers=auth_headers("engineer"))
        assert reload_response.status_code == 200
        reload_payload = reload_response.json()
        assert {"status", "message_count", "signal_count", "hash", "message"} <= reload_payload.keys()
        assert client.post("/api/v1/config/import", json={"source": "test"}, headers=auth_headers("engineer")).status_code == 200
        assert client.get("/api/v1/config/export", headers=auth_headers("viewer")).status_code == 200
        assert client.get("/api/v1/storage/stats", headers=auth_headers("viewer")).status_code == 200
        assert client.get("/api/v1/storage/trend", headers=auth_headers("viewer")).status_code == 200
        assert client.post("/api/v1/storage/cleanup", json={}, headers=auth_headers("admin")).status_code == 200
        assert client.get("/api/v1/system/version", headers=auth_headers("viewer")).status_code == 200
        assert client.get("/api/v1/auth/roles", headers=auth_headers("viewer")).status_code == 200
