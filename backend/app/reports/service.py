from __future__ import annotations

import base64
import csv
from datetime import datetime, timedelta
import json
from pathlib import Path
import shutil
from typing import Any
import uuid

from fastapi import HTTPException

from app.api.data_source import dashboard_metadata
from app.api.errors import get_trace_id
from app.core.paths import DATA_DIR, REPORTS_DIR
from app.core.time import utc_now
from app.services.file_access import (
    human_size,
    normalize_allowed_path,
    sha256_file,
)


class ReportService:
    def __init__(self, app_state: Any) -> None:
        self.state = app_state
        self.output_dir = Path(
            getattr(app_state.reports, "output_dir", REPORTS_DIR)
        ).resolve(strict=False)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def set_output_dir(self, value: str | Path) -> Path:
        path = normalize_allowed_path(
            value,
            [DATA_DIR, self.output_dir],
            must_exist=True,
            expect_file=False,
        )
        self.output_dir = path
        self.state.reports.output_dir = path
        if self.state.preferences:
            self.state.preferences.set("report_directory", str(path))
        return path

    def report_row(self, report_id: str) -> dict[str, Any]:
        row = self.state.repositories.report(report_id) if self.state.repositories else None
        if row is None:
            raise HTTPException(
                404,
                {
                    "code": "REPORT_NOT_FOUND",
                    "message": "报告记录不存在",
                    "details": {"report_id": report_id},
                },
            )
        path = normalize_allowed_path(
            row["file_path"], [self.output_dir, REPORTS_DIR], expect_file=True
        )
        return {**row, "_path": path}

    @staticmethod
    def _result(value: Any) -> str:
        result = str(value or "UNKNOWN").upper()
        return {"PASSED": "PASS", "FAILED": "FAIL"}.get(result, result)

    def report_item(self, row: dict[str, Any]) -> dict[str, Any]:
        path = Path(row["file_path"])
        size = path.stat().st_size if path.is_file() else int(row.get("file_size_bytes") or 0)
        return {
            "report_id": row["id"],
            "session_id": row["session_id"],
            "chassis_no": row.get("chassis_no") or "-",
            "vin": row.get("vin") or "-",
            "test_time": row.get("generated_at") or row.get("created_at") or "-",
            "result": self._result(row.get("result")),
            "operator": row.get("generated_by") or "-",
            "type": f'.{str(row.get("report_type") or path.suffix).lstrip(".")}',
            "size": human_size(size),
            "size_bytes": size,
            "path": str(path),
            "generation_status": row.get("generation_status") or "UNKNOWN",
            "file_hash": row.get("file_hash") or (sha256_file(path) if path.is_file() else None),
        }

    def list_reports(
        self,
        *,
        chassis_no: str | None = None,
        vin: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        result: str | None = None,
        operator: str | None = None,
        file_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if self.state.database is None:
            return []
        clauses = ["1=1"]
        params: list[Any] = []
        for column, value in (("chassis_no", chassis_no), ("vin", vin), ("generated_by", operator)):
            if value and str(value).upper() != "ALL":
                clauses.append(f"{column} LIKE ?")
                params.append(f"%{value}%")
        if start_time:
            clauses.append("generated_at >= ?")
            params.append(start_time)
        if end_time:
            clauses.append("generated_at <= ?")
            params.append(end_time)
        if result and result.upper() != "ALL":
            clauses.append("result = ?")
            params.append(result.upper())
        if file_type and file_type.upper() != "ALL":
            clauses.append("report_type = ?")
            params.append(file_type.lower().lstrip("."))
        rows = self.state.database.query(
            f"SELECT * FROM reports WHERE {' AND '.join(clauses)} ORDER BY generated_at DESC LIMIT 500",
            params,
        )
        return [self.report_item(row) for row in rows if Path(row["file_path"]).is_file()]

    def directory_stats(self) -> dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(self.output_dir)
        files = [path for path in self.output_dir.rglob("*") if path.is_file()]
        counts: dict[str, int] = {}
        for path in files:
            suffix = path.suffix.lower() or ".bin"
            counts[suffix] = counts.get(suffix, 0) + 1
        total_files = sum(counts.values())
        type_stats = [
            {
                "type": file_type,
                "count": count,
                "percent": round(count / total_files * 100, 1) if total_files else 0.0,
            }
            for file_type, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        ]
        last_scan = max((path.stat().st_mtime for path in files), default=0)
        return {
            "path": str(self.output_dir),
            "total_gb": round(usage.total / 1024**3, 2),
            "used_gb": round(usage.used / 1024**3, 2),
            "free_gb": round(usage.free / 1024**3, 2),
            "used_percent": round(usage.used / usage.total * 100, 1) if usage.total else 0.0,
            "last_scan_time": datetime.fromtimestamp(last_scan).isoformat(timespec="seconds") if last_scan else "-",
            "scan_status": "扫描完成",
            "file_type_stats": type_stats,
        }

    def charts(self) -> dict[str, Any]:
        dates = [(datetime.now().date() - timedelta(days=offset)) for offset in range(6, -1, -1)]
        files_by_date: dict[str, int] = {date.isoformat(): 0 for date in dates}
        for path in self.output_dir.rglob("*"):
            if not path.is_file():
                continue
            key = datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
            if key in files_by_date:
                files_by_date[key] += path.stat().st_size
        usage = shutil.disk_usage(self.output_dir)
        cumulative = 0
        trend = []
        for date in dates:
            cumulative += files_by_date[date.isoformat()]
            trend.append(
                {
                    "date": date.strftime("%m-%d"),
                    "used": round(cumulative / 1024**3, 4),
                    "free": round(usage.free / 1024**3, 2),
                }
            )
        distribution = []
        if self.state.database:
            rows = self.state.database.query(
                "SELECT result,COUNT(DISTINCT session_id) AS count FROM reports GROUP BY result"
            )
            total = sum(int(row["count"]) for row in rows)
            by_result = {self._result(row["result"]): int(row["count"]) for row in rows}
            for name in ("PASS", "FAIL"):
                value = by_result.get(name, 0)
                distribution.append(
                    {
                        "name": name,
                        "value": value,
                        "percent": round(value / total * 100, 1) if total else 0.0,
                    }
                )
        return {"storage_trend": trend, "result_distribution": distribution}

    def dashboard(self) -> dict[str, Any]:
        reports = self.list_reports()
        selected = next((row for row in reports if row["type"] == ".pdf"), reports[0] if reports else None)
        quality = "good" if reports else "unavailable"
        return {
            **dashboard_metadata("sqlite+filesystem", quality=quality),
            "directory": self.directory_stats(),
            "reports": reports,
            "selected_report": self.preview(selected["report_id"]) if selected else None,
            "related_data": self.related_data(selected["report_id"]) if selected else {"sessions": []},
            "charts": self.charts(),
        }

    def preview(self, report_id: str) -> dict[str, Any]:
        row = self.report_row(report_id)
        path: Path = row["_path"]
        session = self.state.repositories.session(row["session_id"]) if self.state.repositories else None
        result = self._result(row.get("result"))
        preview = {
            "title": "低速无人车线控底盘生产下线检测报告",
            "chassis_no": row.get("chassis_no") or (session or {}).get("chassis_no") or "-",
            "vin": row.get("vin") or (session or {}).get("vin") or "-",
            "test_time": row.get("generated_at") or "-",
            "result": result,
            "operator": row.get("generated_by") or (session or {}).get("operator") or "-",
            "page": 1,
            "total_pages": 1,
            "zoom": 100,
        }
        json_summary = None
        csv_rows = None
        document_text = None
        image_data = None
        suffix = path.suffix.lower()
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            json_summary = {
                "schema_version": payload.get("schema_version"),
                "generated_at": payload.get("generated_at"),
                "summary": payload.get("summary"),
                "traceability": payload.get("traceability"),
                "session": payload.get("session"),
            }
            document_text = [json.dumps(json_summary, ensure_ascii=False, indent=2, default=str)]
        elif suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                csv_rows = list(csv.DictReader(stream))[:100]
            document_text = [f"CSV rows: {len(csv_rows)}"]
        elif suffix == ".docx":
            from docx import Document

            document = Document(path)
            document_text = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        elif suffix == ".pdf":
            import fitz

            document = fitz.open(path)
            try:
                preview["total_pages"] = document.page_count
                page = document.load_page(0)
                document_text = [line for line in page.get_text("text").splitlines() if line.strip()]
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
                image_data = "data:image/png;base64," + base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            finally:
                document.close()
        return {
            **dashboard_metadata("filesystem", quality="good"),
            "report_id": report_id,
            "filename": path.name,
            "file_type": suffix.lstrip("."),
            "file_sha256": sha256_file(path),
            "file_size_bytes": path.stat().st_size,
            "preview": preview,
            "json_summary": json_summary,
            "csv_rows": csv_rows,
            "document_text": document_text,
            "preview_image_data_url": image_data,
        }

    def related_data(self, report_id: str) -> dict[str, Any]:
        row = self.report_row(report_id)
        session_id = row["session_id"]
        session = self.state.repositories.session(session_id) if self.state.repositories else None
        if session is None:
            raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "报告关联会话不存在", "details": {"session_id": session_id}})
        database = self.state.database
        counts = {}
        for table in ("test_steps", "test_assertions", "raw_can_frames", "decoded_signals", "alarms", "operator_actions", "reports"):
            result = database.query_one(f"SELECT COUNT(*) AS count FROM {table} WHERE session_id=?", (session_id,))
            counts[table] = int(result["count"] if result else 0)
        return {
            "report_id": report_id,
            "sessions": [
                {
                    "session_id": session_id,
                    "started_at": session.get("started_at") or "-",
                    "ended_at": session.get("ended_at") or "-",
                    "result": self._result(session.get("overall_result") or session.get("status")),
                    "report_count": counts["reports"],
                }
            ],
            "counts": counts,
            **dashboard_metadata("sqlite", quality="good"),
        }

    def scan(self) -> dict[str, Any]:
        files = [path for path in self.output_dir.rglob("*") if path.is_file()]
        indexed_rows = self.state.database.query("SELECT id,file_path FROM reports") if self.state.database else []
        indexed = {str(Path(row["file_path"]).resolve(strict=False)): row["id"] for row in indexed_rows}
        disk_paths = {str(path.resolve(strict=False)) for path in files}
        return {
            "file_count": len(files),
            "indexed_count": sum(path in indexed for path in disk_paths),
            "unindexed_files": [str(path) for path in sorted(disk_paths - set(indexed))],
            "missing_files": [
                {"report_id": report_id, "path": path}
                for path, report_id in indexed.items()
                if path not in disk_paths
            ],
            "scanned_at": utc_now(),
        }

    def find_session_report(self, session_id: str, report_type: str) -> dict[str, Any] | None:
        if self.state.database is None:
            return None
        return self.state.database.query_one(
            "SELECT * FROM reports WHERE session_id=? AND report_type=? ORDER BY generated_at DESC LIMIT 1",
            (session_id, report_type),
        )

    def export_target(self, report_id: str, report_type: str) -> dict[str, Any]:
        row = self.report_row(report_id)
        target = self.find_session_report(row["session_id"], report_type)
        if target is None or not Path(target["file_path"]).is_file():
            generated = self.regenerate(report_id)
            target_id = next(
                (item for item in generated["database_ids"] if item.endswith(f"-{report_type}")),
                None,
            )
            if not target_id:
                raise HTTPException(500, {"code": "REPORT_FORMAT_FAILED", "message": f"无法生成 {report_type.upper()} 报告", "details": {"report_id": report_id}})
            target = self.report_row(target_id)
        else:
            target = self.report_row(target["id"])
        path: Path = target["_path"]
        return {
            "report_id": target["id"],
            "file_name": path.name,
            "file_size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "download_url": f'/reports/{target["id"]}/file',
        }

    def regenerate(self, report_id: str) -> dict[str, Any]:
        row = self.report_row(report_id)
        bundle = self.state.repositories.session_bundle(row["session_id"]) if self.state.repositories else None
        if bundle is None:
            raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "报告关联会话不存在", "details": {"session_id": row["session_id"]}})
        session = bundle["session"]
        metadata = {
            "software_version": session.get("software_version"),
            "dbc_hash": session.get("dbc_hash"),
            "config_hash": session.get("config_hash"),
            "test_plan_id": session.get("test_plan_id"),
            "test_plan_version": session.get("plan_version"),
            "operator": session.get("operator"),
        }
        generated = self.state.reports.generate(session, bundle["steps"], metadata=metadata)
        database_ids = self.state.eol_uow.persist_report(session, generated)
        return {**generated, "database_ids": database_ids}

    def create_print_job(self, report_id: str, requested_by: str) -> dict[str, Any]:
        row = self.report_row(report_id)
        target = row
        if row["report_type"] != "pdf":
            pdf = self.find_session_report(row["session_id"], "pdf")
            if pdf is None:
                generated = self.regenerate(report_id)
                pdf_id = next(item for item in generated["database_ids"] if item.endswith("-pdf"))
                target = self.report_row(pdf_id)
            else:
                target = self.report_row(pdf["id"])
        job_id = f"PRINT-{uuid.uuid4().hex[:12].upper()}"
        now = utc_now()
        self.state.database.execute(
            "INSERT INTO report_print_jobs(id,report_id,file_path,requested_by,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (job_id, target["id"], str(target["_path"]), requested_by, "QUEUED", now, now),
        )
        return {
            "job_id": job_id,
            "report_id": target["id"],
            "status": "QUEUED",
            "file_name": target["_path"].name,
            "created_at": now,
        }

    def print_job(self, job_id: str) -> dict[str, Any]:
        row = self.state.database.query_one("SELECT * FROM report_print_jobs WHERE id=?", (job_id,)) if self.state.database else None
        if row is None:
            raise HTTPException(404, {"code": "PRINT_JOB_NOT_FOUND", "message": "打印任务不存在", "details": {"job_id": job_id}})
        return row

    def delete(self, report_id: str) -> dict[str, Any]:
        row = self.report_row(report_id)
        path: Path = row["_path"]
        path.unlink()
        self.state.database.execute("DELETE FROM reports WHERE id=?", (report_id,))
        return {"report_id": report_id, "path": str(path), "deleted": True}
