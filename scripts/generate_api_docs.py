from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.routing import APIRoute

from app.configuration.models import ProductionConfiguration, SignedConfigurationPackage
from app.main import app
from app.security.auth import ROLE_LEVEL, Role


PUBLIC = {
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/auth/bootstrap/status"),
    ("POST", "/api/v1/auth/bootstrap"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/unlock"),
}


def data_class(method: str, path: str) -> str:
    if path.endswith("/health"):
        return "public-minimal"
    if path.startswith("/api/v1/auth"):
        return "identity-credential" if (method, path) in PUBLIC else "identity-sensitive"
    if method == "GET":
        return "operational-sensitive"
    if path.startswith("/api/v1/config") or path.startswith("/api/v1/maintenance"):
        return "configuration-privileged"
    if path.startswith("/api/v1/control") or path.startswith("/api/v1/can"):
        return "motion-or-transport-privileged"
    return "business-write-privileged"


def minimum_role(route: APIRoute, method: str, path: str, inherited_dependencies: list[Any]) -> str:
    if (method, path) in PUBLIC:
        return "public"
    roles: list[Role] = []
    dependencies = [dependency.call for dependency in route.dependant.dependencies]
    dependencies.extend(getattr(dependency, "dependency", None) for dependency in inherited_dependencies)
    for dependency in dependencies:
        minimum = getattr(dependency, "minimum_role", None)
        if minimum is not None:
            roles.append(minimum)
    return max(roles, key=lambda item: ROLE_LEVEL[item]).value if roles else "UNCLASSIFIED"


def api_routes(router: Any, prefix: str = "", inherited_dependencies: list[Any] | None = None):
    inherited_dependencies = inherited_dependencies or []
    for route in router.routes:
        if isinstance(route, APIRoute):
            yield route, f"{prefix}{route.path}", inherited_dependencies
            continue
        original = getattr(route, "original_router", None)
        context = getattr(route, "include_context", None)
        if original is None or context is None:
            continue
        next_prefix = context.prefix or prefix
        next_dependencies = [*inherited_dependencies, *context.dependencies]
        yield from api_routes(original, next_prefix, next_dependencies)


def main() -> int:
    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    schemas = {
        "ProductionConfiguration": ProductionConfiguration.model_json_schema(),
        "SignedConfigurationPackage": SignedConfigurationPackage.model_json_schema(),
    }
    (docs / "production-configuration.schema.json").write_text(
        json.dumps(schemas, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rows: list[dict[str, Any]] = []
    for route, effective_path, inherited_dependencies in api_routes(app.router):
        if not effective_path.startswith("/api/v1"):
            continue
        for method in sorted(route.methods or []):
            if method in {"HEAD", "OPTIONS"}:
                continue
            rows.append(
                {
                    "method": method,
                    "path": effective_path,
                    "data_class": data_class(method, effective_path),
                    "minimum_role": minimum_role(route, method, effective_path, inherited_dependencies),
                    "operation_id": route.operation_id or route.name,
                }
            )
    rows.sort(key=lambda item: (item["path"], item["method"]))
    with (docs / "api-authorization-matrix.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if any(row["minimum_role"] == "UNCLASSIFIED" for row in rows):
        missing = [f'{row["method"]} {row["path"]}' for row in rows if row["minimum_role"] == "UNCLASSIFIED"]
        raise RuntimeError(f"API authorization inventory has unclassified routes: {missing}")
    print(f"generated OpenAPI and authorization inventory for {len(rows)} operations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
