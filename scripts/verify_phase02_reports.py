from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sqlite3
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile_results = json.loads(args.profiles.read_text(encoding="utf-8"))
    connection = sqlite3.connect(ROOT / "data" / "chassis_eol.db")
    connection.row_factory = sqlite3.Row
    reports = []
    for profile, result in profile_results["profiles"].items():
        session_id = result["session_id"]
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT report_type,file_path,file_size_bytes,file_hash,generation_status "
                "FROM reports WHERE session_id=? ORDER BY report_type",
                (session_id,),
            )
        ]
        by_type = {row["report_type"]: row for row in rows}
        json_path = Path(by_type["json"]["file_path"])
        docx_path = Path(by_type["docx"]["file_path"])
        pdf_path = Path(by_type["pdf"]["file_path"])
        csv_path = Path(by_type["csv"]["file_path"])
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        with zipfile.ZipFile(docx_path) as archive:
            docx_ok = archive.testzip() is None and "word/document.xml" in archive.namelist()
        pdf_ok = pdf_path.read_bytes().startswith(b"%PDF")
        with csv_path.open(encoding="utf-8-sig") as fp:
            csv_rows = list(csv.DictReader(fp))
        steps = payload.get("steps", [])
        item = {
            "profile": profile,
            "session_id": session_id,
            "database_report_rows": len(rows),
            "types": sorted(by_type),
            "all_completed": all(row["generation_status"] == "COMPLETED" for row in rows),
            "json_opened": True,
            "json_result": payload.get("session", {}).get("overall_result"),
            "json_step_count": len(steps),
            "json_last_step_result": steps[-1].get("result") if steps else None,
            "traceability": payload.get("traceability", {}),
            "docx_opened": docx_ok,
            "pdf_opened": pdf_ok,
            "csv_rows": len(csv_rows),
        }
        item["passed"] = all(
            [
                len(rows) == 4,
                sorted(by_type) == ["csv", "docx", "json", "pdf"],
                item["all_completed"],
                docx_ok,
                pdf_ok,
                bool(csv_rows),
                len(steps) == result["actual"]["step_count"],
                bool(item["traceability"].get("dbc_hash")),
                bool(item["traceability"].get("test_plan_version")),
            ]
        )
        reports.append(item)
    connection.close()
    output = {
        "reports": reports,
        "all_passed": all(item["passed"] for item in reports),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
