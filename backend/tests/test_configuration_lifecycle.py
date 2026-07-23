import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.api import config as config_api
from app.configuration.models import SignedConfigurationPackage, sign_package
from app.main import app
from app.services.app_state import state


@pytest.fixture(autouse=True)
def clean_active_package():
    path = Path(os.environ["CHASSIS_ACTIVE_CONFIG_PATH"])
    original_config = state.config
    path.unlink(missing_ok=True)
    yield
    path.unlink(missing_ok=True)
    state.config = original_config


def _export(client: TestClient, auth_headers) -> dict:
    response = client.get("/api/v1/config/export", headers=auth_headers("admin"))
    assert response.status_code == 200
    return response.json()["package"]


def _resign(package: dict, **configuration_updates) -> dict:
    package = {**package, "configuration": {**package["configuration"], **configuration_updates}}
    parsed = SignedConfigurationPackage.model_validate(package)
    signature = sign_package(parsed, os.environ["CHASSIS_CONFIG_SIGNING_KEY"])
    return parsed.model_copy(update={"signature": signature}).model_dump(mode="json")


def test_signed_export_dry_run_and_admin_permission(auth_headers):
    with TestClient(app) as client:
        package = _export(client, auth_headers)
        assert package["schema_version"] == 2
        assert package["signature_algorithm"] == "HMAC-SHA256"
        request = {"package": package, "dry_run": True}
        assert client.post("/api/v1/config/import", json=request, headers=auth_headers("engineer")).status_code == 403
        preview = client.post("/api/v1/config/import", json=request, headers=auth_headers("admin"))
        assert preview.status_code == 200
        assert preview.json()["signature_valid"] is True
        assert preview.json()["schema_valid"] is True
        assert preview.json()["blocking_checks"] == []


def test_invalid_old_schema_and_signature_are_rejected(auth_headers):
    with TestClient(app) as client:
        package = _export(client, auth_headers)
        old = {**package, "schema_version": 0}
        assert client.post("/api/v1/config/import", json={"package": old}, headers=auth_headers("admin")).status_code == 422
        malformed = {**package, "configuration": {**package["configuration"], "can_endpoints": []}}
        assert client.post("/api/v1/config/import", json={"package": malformed}, headers=auth_headers("admin")).status_code == 422
        tampered = {**package, "configuration": {**package["configuration"], "station_id": "TAMPERED"}}
        response = client.post("/api/v1/config/import", json={"package": tampered}, headers=auth_headers("admin"))
        assert response.status_code == 422
        assert response.json()["code"] == "CONFIG_SIGNATURE_INVALID"


def test_production_template_dbc_placeholder_is_rejected(auth_headers):
    with TestClient(app) as client:
        package = _export(client, auth_headers)
        placeholder = {
            **package,
            "configuration": {
                **package["configuration"],
                "runtime_profile": "production",
                "approved_dbc_sha256": "0" * 64,
            },
        }
        response = client.post(
            "/api/v1/config/import",
            json={"package": placeholder, "dry_run": True},
            headers=auth_headers("admin"),
        )
        assert response.status_code == 422
        assert "template placeholder" in str(response.json())


def test_apply_persists_package_and_reports_restart_requirement(auth_headers, tmp_path: Path):
    with TestClient(app) as client:
        package = _export(client, auth_headers)
        package = _resign(package, config_version="test-package-v2", data_root=str(tmp_path / "new-data-root"))
        preview = client.post("/api/v1/config/import", json={"package": package}, headers=auth_headers("admin"))
        assert preview.status_code == 200
        response = client.post(
            "/api/v1/config/apply",
            json={"package": package, "confirmation": "APPLY", "reason": "loopback lifecycle test"},
            headers=auth_headers("admin"),
        )
        assert response.status_code == 200
        assert response.json()["applied"] is True
        assert response.json()["requires_restart"] is True
        assert Path(os.environ["CHASSIS_ACTIVE_CONFIG_PATH"]).exists()
        assert state.config.config_version == "test-package-v2"
        from app.services.lifecycle import on_can_security_event

        assert all(
            getattr(gateway, "on_security_event", None) is on_can_security_event
            for gateway in state.can.gateways.values()
            if hasattr(gateway, "on_security_event")
        )


def test_apply_failure_restores_runtime_and_previous_package(auth_headers, monkeypatch: pytest.MonkeyPatch):
    with TestClient(app) as client:
        package = _export(client, auth_headers)
        package = _resign(package, config_version="rollback-candidate")
        old_config = state.config
        monkeypatch.setattr(config_api, "persist_active_package", lambda _package: (_ for _ in ()).throw(OSError("injected persistence failure")))
        response = client.post(
            "/api/v1/config/apply",
            json={"package": package, "confirmation": "APPLY", "reason": "rollback injection"},
            headers=auth_headers("admin"),
        )
        assert response.status_code == 503
        assert response.json()["code"] == "CONFIG_APPLY_ROLLED_BACK"
        assert state.config is old_config
        assert not Path(os.environ["CHASSIS_ACTIVE_CONFIG_PATH"]).exists()
