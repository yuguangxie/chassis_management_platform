from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "audit"
OUTPUT = AUDIT / "evidence" / "tests" / "audit_bundle_validation.json"

REQUIRED = [
    "AUDIT_INDEX.md",
    "00_EXECUTIVE_SUMMARY.md",
    "01_PROJECT_BASELINE.md",
    "02_UI_FIDELITY_AUDIT.md",
    "03_PAGE_FUNCTION_AUDIT.md",
    "04_FRONTEND_ARCHITECTURE_AUDIT.md",
    "05_BACKEND_API_AUDIT.md",
    "06_CAN_DBC_PROTOCOL_AUDIT.md",
    "07_SIMULATION_E2E_AUDIT.md",
    "08_EOL_TEST_ENGINE_AUDIT.md",
    "09_DATABASE_LOG_REPORT_AUDIT.md",
    "10_SECURITY_SAFETY_AUDIT.md",
    "11_TEST_QUALITY_AUDIT.md",
    "12_PERFORMANCE_RELIABILITY_AUDIT.md",
    "13_PACKAGING_DEPLOYMENT_AUDIT.md",
    "14_ISSUE_REGISTER.md",
    "15_REMEDIATION_PLAN.md",
    "AUDIT_MANIFEST.md",
    "audit_results.json",
    "issue_register.csv",
]


def main() -> None:
    failures: list[str] = []
    checks: dict[str, object] = {}

    required_status = {}
    for relative in REQUIRED:
        path = AUDIT / relative
        ok = path.is_file() and path.stat().st_size > 0
        required_status[relative] = {"exists": path.is_file(), "bytes": path.stat().st_size if path.is_file() else 0, "ok": ok}
        if not ok:
            failures.append(f"required file missing/empty: {relative}")
    entry = ROOT / "docs" / "AUDIT_REPORT.md"
    if not entry.is_file() or entry.stat().st_size == 0:
        failures.append("docs/AUDIT_REPORT.md missing/empty")
    checks["required_files"] = required_status

    try:
        audit_results = json.loads((AUDIT / "audit_results.json").read_text(encoding="utf-8"))
        checks["audit_results"] = {
            "valid_json": True,
            "page_count": len(audit_results.get("pages", [])),
            "issue_counts": audit_results.get("issues"),
            "production_readiness": audit_results.get("production_readiness"),
        }
        if len(audit_results.get("pages", [])) != 11:
            failures.append("audit_results pages != 11")
    except Exception as exc:
        checks["audit_results"] = {"valid_json": False, "error": str(exc)}
        failures.append(f"invalid audit_results.json: {exc}")

    with (AUDIT / "issue_register.csv").open("r", encoding="utf-8-sig", newline="") as fp:
        issue_rows = list(csv.DictReader(fp))
    checks["issue_csv"] = {"row_count": len(issue_rows), "headers": list(issue_rows[0]) if issue_rows else []}
    if len(issue_rows) != 42:
        failures.append(f"issue CSV rows={len(issue_rows)}, expected 42")
    for row in issue_rows:
        for evidence in [value.strip() for value in row["evidence"].split(";") if value.strip()]:
            path = AUDIT / evidence
            if not path.exists():
                failures.append(f"issue {row['issue_id']} missing evidence: {evidence}")

    screenshot_dir = AUDIT / "evidence" / "screenshots" / "current"
    online = sorted(path for path in screenshot_dir.glob("[0-1][0-9]_*.png") if not path.name.startswith("offline_"))
    dimensions = {}
    for path in online:
        with Image.open(path) as image:
            dimensions[path.name] = list(image.size)
            expected = (1920, 1080) if "1920x1080" in path.name else (1366, 768)
            if image.size != expected:
                failures.append(f"bad screenshot dimensions {path.name}: {image.size} != {expected}")
    checks["screenshots"] = {
        "online_count": len(online),
        "reference_count": len(list((AUDIT / "evidence" / "screenshots" / "reference").glob("*.png"))),
        "diff_composite_count": len(list((AUDIT / "evidence" / "screenshots" / "diff").glob("*_reference_current_diff.png"))),
        "dimensions": dimensions,
    }
    if len(online) != 22:
        failures.append(f"online screenshot count={len(online)}, expected 22")
    if checks["screenshots"]["reference_count"] != 10:
        failures.append("reference screenshot count != 10")
    if checks["screenshots"]["diff_composite_count"] != 10:
        failures.append("diff composite count != 10")

    markdown_link_failures = []
    link_pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for document in AUDIT.glob("*.md"):
        for target in link_pattern.findall(document.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#")):
                continue
            resolved = (document.parent / target).resolve()
            if not resolved.exists():
                markdown_link_failures.append({"document": document.name, "target": target})
    checks["markdown_links"] = {"missing": markdown_link_failures}
    failures.extend(f"broken link {item['document']} -> {item['target']}" for item in markdown_link_failures)

    report_text = (AUDIT / "02_UI_FIDELITY_AUDIT.md").read_text(encoding="utf-8")
    function_text = (AUDIT / "03_PAGE_FUNCTION_AUDIT.md").read_text(encoding="utf-8")
    routes = ["/overview", "/network-config", "/can-monitor", "/signal-dashboard", "/realtime-curve", "/manual-control", "/auto-test", "/alarm-diagnosis", "/report-management", "/history", "/system-settings"]
    checks["route_coverage"] = {
        "ui": {route: route in report_text for route in routes},
        "function": {route: route in function_text for route in routes},
    }
    if not all(checks["route_coverage"]["ui"].values()):
        failures.append("UI audit does not include all 11 routes")
    if not all(checks["route_coverage"]["function"].values()):
        failures.append("function audit does not include all 11 routes")

    result = {"ok": not failures, "failure_count": len(failures), "failures": failures, "checks": checks}
    if "--no-write" not in sys.argv:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "failure_count": len(failures), "failures": failures[:20]}, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
