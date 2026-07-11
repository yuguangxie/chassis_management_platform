from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT.parent
SPEC_PATH = PACK / "docs" / "07_api_spec.md"
OPENAPI_PATH = ROOT / "docs" / "audit" / "evidence" / "api" / "openapi_response.json"
OUT = ROOT / "docs" / "audit" / "evidence" / "api" / "api_spec_comparison.json"


def normalize_path(path: str) -> str:
    path = path if path.startswith("/api/v1") else "/api/v1" + path
    return re.sub(r"\{[^}]+\}", "{}", path)


def main() -> int:
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    requirements = []
    for method, path in re.findall(r"\|\s*(GET|POST|PUT|DELETE|PATCH)\s*\|\s*`([^`]+)`", spec_text, re.I):
        requirements.append({"method": method.upper(), "path": path, "normalized_path": normalize_path(path)})
    openapi_wrapper = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    openapi = openapi_wrapper["body"]
    implemented = []
    for path, operations in openapi.get("paths", {}).items():
        for method, operation in operations.items():
            if method.upper() not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                continue
            implemented.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "normalized_path": normalize_path(path),
                    "operation_id": operation.get("operationId"),
                    "has_request_body": bool(operation.get("requestBody")),
                    "response_codes": sorted(operation.get("responses", {}).keys()),
                }
            )
    implemented_keys = {(item["method"], item["normalized_path"]) for item in implemented}
    required_keys = {(item["method"], item["normalized_path"]) for item in requirements}
    missing = [item for item in requirements if (item["method"], item["normalized_path"]) not in implemented_keys]
    extra = [item for item in implemented if (item["method"], item["normalized_path"]) not in required_keys]
    exact_path_mismatches = []
    for requirement in requirements:
        semantic = [item for item in implemented if item["method"] == requirement["method"] and item["normalized_path"] == requirement["normalized_path"]]
        if semantic and all(item["path"] != (requirement["path"] if requirement["path"].startswith("/api/v1") else "/api/v1" + requirement["path"]) for item in semantic):
            exact_path_mismatches.append({"spec": requirement, "implemented": semantic})
    result = {
        "audit_time": datetime.now().astimezone().isoformat(),
        "spec_source": str(SPEC_PATH),
        "spec_endpoint_count": len(requirements),
        "openapi_endpoint_count": len(implemented),
        "implemented_spec_endpoints": len(requirements) - len(missing),
        "spec_coverage_percent": round((len(requirements) - len(missing)) / len(requirements) * 100, 1) if requirements else 0,
        "missing": missing,
        "extra_not_in_core_spec": extra,
        "path_parameter_name_mismatches": exact_path_mismatches,
        "requirements": requirements,
        "implemented": implemented,
        "manual_contract_findings": [
            "The specification requires trace_id in every response; most successful responses omit it.",
            "The specification wraps errors under error; runtime endpoints use a mix of detail, flat dictionaries, and the global flat error format.",
            "The 0x121 preview request example uses drive_mode=auto_drive_request and nested lights; the Pydantic model accepts Manual/Remote/Auto and flat light fields.",
            "The 0x121 preview specification returns allowed/interlocks and one bytes_hex string; runtime returns data plus a second, inconsistent bytes_hex display array without interlocks.",
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("spec_endpoint_count", "openapi_endpoint_count", "implemented_spec_endpoints", "spec_coverage_percent", "missing", "path_parameter_name_mismatches")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
