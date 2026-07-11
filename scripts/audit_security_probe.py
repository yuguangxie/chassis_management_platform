from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "audit" / "evidence" / "api"
BASE_URL = "http://127.0.0.1:8800"


def response_summary(response: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text[:1000]
    return {
        "status_code": response.status_code,
        "headers": {
            key: value
            for key, value in response.headers.items()
            if key.lower().startswith("access-control") or key.lower() in {"content-type"}
        },
        "body": body,
    }


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        openapi = client.get("/openapi.json")
        openapi_body = openapi.json()
        results["openapi_authentication"] = {
            "security_schemes": openapi_body.get("components", {}).get("securitySchemes"),
            "global_security": openapi_body.get("security"),
        }

        results["unauthenticated_role_state"] = response_summary(client.get("/api/v1/auth/roles"))

        # Establish a known safe state before probing privileged routes.
        results["unauthenticated_maintenance_exit_before"] = response_summary(
            client.post("/api/v1/maintenance/exit", json={"role": "admin", "reason": "audit safe-state reset"})
        )

        results["dangerous_feature_without_maintenance"] = response_summary(
            client.put(
                "/api/v1/maintenance/features",
                json={
                    "role": "admin",
                    "reason": "audit gate verification",
                    "confirmation": "MAINTENANCE",
                    "enable_0x123": True,
                },
            )
        )

        results["unauthenticated_maintenance_enter"] = response_summary(
            client.post(
                "/api/v1/maintenance/enter",
                json={"role": "admin", "confirmation": "MAINTENANCE", "reason": "audit authentication verification"},
            )
        )

        results["spoofed_admin_delete_nonexistent"] = response_summary(
            client.delete("/api/v1/reports/AUDIT-NONEXISTENT-REPORT", headers={"x-role": "admin"})
        )
        results["default_role_delete_nonexistent"] = response_summary(
            client.delete("/api/v1/reports/AUDIT-NONEXISTENT-REPORT")
        )

        results["cors_arbitrary_origin"] = response_summary(
            client.options(
                "/api/v1/health",
                headers={
                    "origin": "https://audit-untrusted.example",
                    "access-control-request-method": "GET",
                    "access-control-request-headers": "authorization,content-type",
                },
            )
        )

        # Always leave the process in the safe default state.
        results["unauthenticated_maintenance_exit_after"] = response_summary(
            client.post("/api/v1/maintenance/exit", json={"role": "admin", "reason": "audit cleanup"})
        )
        results["maintenance_state_after_cleanup"] = response_summary(client.get("/api/v1/config/system-dashboard"))

    output = EVIDENCE / "security_probe.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "auth_scheme_present": bool(results["openapi_authentication"]["security_schemes"]),
        "unauthenticated_backend_role": results["unauthenticated_role_state"]["body"].get("current_role"),
        "maintenance_enter_status": results["unauthenticated_maintenance_enter"]["status_code"],
        "nonexistent_delete_with_spoofed_admin_status": results["spoofed_admin_delete_nonexistent"]["status_code"],
        "nonexistent_delete_without_role_status": results["default_role_delete_nonexistent"]["status_code"],
        "dangerous_feature_without_maintenance_status": results["dangerous_feature_without_maintenance"]["status_code"],
        "cors_allow_origin": results["cors_arbitrary_origin"]["headers"].get("access-control-allow-origin"),
        "cleanup_exit_status": results["unauthenticated_maintenance_exit_after"]["status_code"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
