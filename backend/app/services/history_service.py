from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path
from typing import Any
import zipfile

from fastapi import HTTPException

from app.api.data_source import dashboard_metadata
from app.api.errors import get_trace_id
from app.core.time import utc_now
from app.services.file_access import human_size, normalize_allowed_path, sha256_file


DOWNLOAD_TYPES = {
    "raw-can": ("raw_can", "原始 CAN 数据", ".csv"),
    "decoded-signals": ("decoded_signals", "解析后信号数据", ".csv"),
    "report-bundle": ("report_bundle", "报告与数据包", ".zip"),
    "audit-log": ("audit_log", "审计日志", ".json"),
    "curve-replay": ("curve_replay", "曲线回放包", ".zip"),
}


class HistoryService:
    def __init__(self, app_state: Any) -> None:
        self.state = app_state
        self.export_root = app_state.data_paths.exports / "history"
        self.export_root.mkdir(parents=True, exist_ok=True)

    def session_row(self, session_id: str) -> dict[str, Any]:
        row = self.state.repositories.session(session_id) if self.state.repositories else None
        if row is None:
            raise HTTPException(
                404,
                {
                    "code": "SESSION_NOT_FOUND",
                    "message": "检测会话不存在",
                    "details": {"session_id": session_id},
                },
            )
        return row

    @staticmethod
    def result_label(row: dict[str, Any]) -> str:
        result = str(row.get("overall_result") or row.get("status") or "RUNNING").upper()
        return {"PASSED": "PASS", "FAILED": "FAIL", "IDLE": "RUNNING", "EMERGENCY_STOPPED": "ABORTED"}.get(result, result)

    def session_item(self, row: dict[str, Any]) -> dict[str, Any]:
        failed = self.state.database.query_one(
            "SELECT name FROM test_steps WHERE session_id=? AND result='FAIL' ORDER BY step_order LIMIT 1",
            (row["id"],),
        )
        report = self.state.database.query_one(
            "SELECT id FROM reports WHERE session_id=? "
            "ORDER BY CASE WHEN report_type='pdf' THEN 0 ELSE 1 END, generated_at DESC LIMIT 1",
            (row["id"],),
        )
        return {
            "session_id": row["id"],
            "chassis_no": row.get("chassis_no") or "-",
            "vin": row.get("vin") or "-",
            "serial_no": row.get("serial_no") or "-",
            "started_at": row.get("started_at") or row.get("created_at") or "-",
            "ended_at": row.get("ended_at") or "-",
            "result": self.result_label(row),
            "failed_step": failed["name"] if failed else "-",
            "operator": row.get("operator") or "-",
            "station_id": row.get("station_id") or "-",
            "report_id": report["id"] if report else None,
        }

    @staticmethod
    def _filters(
        chassis_no: str | None = None,
        vin: str | None = None,
        serial_no: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        result: str | None = None,
        operator: str | None = None,
        station: str | None = None,
    ) -> tuple[str, list[Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        for column, value in (("chassis_no", chassis_no), ("vin", vin), ("serial_no", serial_no), ("operator", operator), ("station_id", station)):
            if value and str(value).upper() != "ALL":
                clauses.append(f"{column} LIKE ?")
                params.append(f"%{value}%")
        if start_time:
            clauses.append("datetime(COALESCE(started_at,created_at)) >= datetime(?)")
            params.append(start_time)
        if end_time:
            clauses.append("datetime(COALESCE(started_at,created_at)) <= datetime(?)")
            params.append(end_time)
        if result and result.upper() != "ALL":
            wanted = result.upper()
            if wanted == "PASS":
                clauses.append("UPPER(COALESCE(overall_result,status)) IN ('PASS','PASSED')")
            elif wanted == "FAIL":
                clauses.append("UPPER(COALESCE(overall_result,status)) IN ('FAIL','FAILED')")
            else:
                clauses.append("UPPER(COALESCE(overall_result,status)) = ?")
                params.append(wanted)
        return " AND ".join(clauses), params

    def sessions(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        **filters: Any,
    ) -> tuple[list[dict[str, Any]], int]:
        where, params = self._filters(**filters)
        total_row = self.state.database.query_one(
            f"SELECT COUNT(*) AS count FROM test_sessions WHERE {where}", params
        )
        total = int(total_row["count"] if total_row else 0)
        rows = self.state.database.query(
            f"SELECT * FROM test_sessions WHERE {where} "
            "ORDER BY COALESCE(started_at,created_at) DESC LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        )
        return [self.session_item(row) for row in rows], total

    def summary(self, filtered_count: int) -> dict[str, Any]:
        totals = self.state.database.query_one(
            "SELECT COUNT(*) AS total,"
            "SUM(CASE WHEN UPPER(COALESCE(overall_result,status)) IN ('PASS','PASSED') THEN 1 ELSE 0 END) AS passed,"
            "SUM(CASE WHEN UPPER(COALESCE(overall_result,status)) IN ('FAIL','FAILED') THEN 1 ELSE 0 END) AS failed "
            "FROM test_sessions"
        ) or {"total": 0, "passed": 0, "failed": 0}
        alarm = self.state.database.query_one("SELECT COUNT(*) AS count FROM alarms") or {"count": 0}
        total = int(totals["total"] or 0)
        passed = int(totals["passed"] or 0)
        return {
            "total_tests": total,
            "pass_rate": round(passed / total * 100, 1) if total else 0.0,
            "fail_count": int(totals["failed"] or 0),
            "alarm_count": int(alarm["count"] or 0),
            "filtered_count": filtered_count,
        }

    @staticmethod
    def _duration(started_at: str | None, ended_at: str | None) -> str:
        if not started_at or not ended_at:
            return "--"
        try:
            start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(ended_at).replace("Z", "+00:00"))
        except ValueError:
            return "--"
        seconds = max(0, int((end - start).total_seconds()))
        return f"{seconds // 60}分{seconds % 60:02d}秒"

    def timeline(self, session_id: str) -> list[dict[str, Any]]:
        self.session_row(session_id)
        rows = self.state.database.query(
            "SELECT * FROM test_steps WHERE session_id=? ORDER BY step_order", (session_id,)
        )
        return [
            {
                "time": str(row.get("started_at") or "--")[11:23],
                "title": row.get("name") or row.get("step_id"),
                "description": row.get("measurement_summary") or row.get("command_summary") or row.get("failure_reason") or "步骤执行完成",
                "status": "PASS" if row.get("result") == "PASS" else "FAIL" if row.get("result") == "FAIL" else "RUNNING" if row.get("status") == "RUNNING" else "INFO",
                "icon": self._timeline_icon(str(row.get("name") or "")),
                "step_id": row.get("step_id"),
                "duration_ms": row.get("duration_ms"),
            }
            for row in rows
        ]

    @staticmethod
    def _timeline_icon(name: str) -> str:
        for text, icon in (("CAN", "network"), ("BMS", "battery"), ("转向", "steering"), ("报告", "report"), ("驱动", "gauge"), ("制动", "brake"), ("告警", "alarm")):
            if text in name:
                return icon
        return "settings"

    def operator_logs(self, session_id: str) -> list[dict[str, Any]]:
        self.session_row(session_id)
        rows = self.state.database.query(
            "SELECT * FROM operator_actions WHERE session_id=? ORDER BY timestamp_utc", (session_id,)
        )
        return [
            {
                "time": str(row.get("timestamp_utc") or "--")[11:23],
                "user": row.get("operator") or "-",
                "action": row.get("action_type") or "-",
                "target": row.get("target") or "-",
                "params": row.get("request_json") or "-",
                "result": "成功" if row.get("result") == "OK" else str(row.get("result") or "-"),
                "trace_id": row.get("trace_id") or "",
            }
            for row in rows
        ]

    def _session_export_dir(self, session_id: str) -> Path:
        path = self.export_root / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def download_items(self, session_id: str) -> list[dict[str, Any]]:
        self.session_row(session_id)
        raw_count = int((self.state.database.query_one("SELECT COUNT(*) AS count FROM raw_can_frames WHERE session_id=?", (session_id,)) or {"count": 0})["count"])
        decoded_count = int((self.state.database.query_one("SELECT COUNT(*) AS count FROM decoded_signals WHERE session_id=?", (session_id,)) or {"count": 0})["count"])
        actions = int((self.state.database.query_one("SELECT COUNT(*) AS count FROM operator_actions WHERE session_id=?", (session_id,)) or {"count": 0})["count"])
        reports = self.state.repositories.reports_for_session(session_id)
        availability = {
            "raw-can": raw_count > 0,
            "decoded-signals": decoded_count > 0,
            "report-bundle": bool(reports),
            "audit-log": actions > 0,
            "curve-replay": decoded_count > 0,
        }
        rows = []
        for file_type, (key, name, extension) in DOWNLOAD_TYPES.items():
            existing = self._expected_export_path(session_id, file_type)
            size = existing.stat().st_size if existing.is_file() else sum(int(row.get("file_size_bytes") or 0) for row in reports) if file_type == "report-bundle" else 0
            rows.append(
                {
                    "key": key,
                    "name": name,
                    "extension": extension,
                    "size": human_size(size),
                    "size_bytes": size,
                    "available": availability[file_type],
                    "download_url": f"/test-sessions/{session_id}/download/{file_type}" if availability[file_type] else None,
                }
            )
        return rows

    def selected(self, row: dict[str, Any]) -> dict[str, Any]:
        session = self.session_row(row["session_id"])
        return {
            "session_id": row["session_id"],
            "duration": self._duration(session.get("started_at"), session.get("ended_at")),
            "result": row["result"],
            "timeline": self.timeline(row["session_id"]),
            "operator_logs": self.operator_logs(row["session_id"]),
            "downloads": self.download_items(row["session_id"]),
        }

    def charts(self, vin: str | None = None) -> dict[str, Any]:
        vin = vin or ""
        trend_rows = self.state.database.query(
            "SELECT substr(COALESCE(started_at,created_at),1,10) AS day,"
            "SUM(CASE WHEN UPPER(COALESCE(overall_result,status)) IN ('PASS','PASSED') THEN 1 ELSE 0 END) AS passed,"
            "SUM(CASE WHEN UPPER(COALESCE(overall_result,status)) IN ('FAIL','FAILED') THEN 1 ELSE 0 END) AS failed "
            "FROM test_sessions WHERE (?='' OR vin=?) GROUP BY day ORDER BY day DESC LIMIT 8",
            (vin, vin),
        )
        trend_rows = list(reversed(trend_rows))
        failed_rows = self.state.database.query(
            "SELECT COALESCE(name,step_id) AS reason,COUNT(*) AS count FROM test_steps "
            "WHERE result='FAIL' GROUP BY COALESCE(name,step_id) ORDER BY count DESC LIMIT 8"
        )
        counts = [int(row["count"]) for row in failed_rows]
        total = sum(counts)
        running = 0
        cumulative = []
        for count in counts:
            running += count
            cumulative.append(round(running / total * 100, 1) if total else 0.0)
        return {
            "vehicle_result_trend": {
                "vin": vin or "-",
                "x_axis": [str(row["day"])[5:] for row in trend_rows],
                "pass": [int(row["passed"] or 0) for row in trend_rows],
                "fail": [int(row["failed"] or 0) for row in trend_rows],
            },
            "failure_pareto": {
                "categories": [str(row["reason"]) for row in failed_rows],
                "counts": counts,
                "cumulative_percent": cumulative,
            },
        }

    def dashboard(self, *, page: int, page_size: int, **filters: Any) -> dict[str, Any]:
        items, total = self.sessions(page=page, page_size=page_size, **filters)
        selected = self.selected(items[0]) if items else None
        total_pages = (total + page_size - 1) // page_size if total else 0
        quality = "good" if self.state.database else "unavailable"
        return {
            **dashboard_metadata("sqlite+filesystem", quality=quality),
            "filters": {
                "start_time": filters.get("start_time") or "",
                "end_time": filters.get("end_time") or "",
                "page": page,
                "page_size": page_size,
            },
            "summary": self.summary(total),
            "sessions": items,
            "selected_session": selected,
            "charts": self.charts(items[0]["vin"] if items else filters.get("vin")),
            "pagination": {"page": page, "page_size": page_size, "total": total, "total_pages": total_pages},
        }

    def replay(self, session_id: str) -> dict[str, Any]:
        session = self.session_row(session_id)
        bounds = self.state.database.query_one(
            "SELECT MIN(timestamp_utc) AS start_time,MAX(timestamp_utc) AS end_time,COUNT(*) AS points "
            "FROM decoded_signals WHERE session_id=?",
            (session_id,),
        ) or {}
        start = bounds.get("start_time") or session.get("started_at")
        end = bounds.get("end_time") or session.get("ended_at")
        duration_seconds = 0
        if start and end:
            try:
                duration_seconds = max(0, int((datetime.fromisoformat(str(end).replace("Z", "+00:00")) - datetime.fromisoformat(str(start).replace("Z", "+00:00"))).total_seconds()))
            except ValueError:
                duration_seconds = 0
        return {
            "session_id": session_id,
            "data_source": "SQLite decoded_signals",
            "timezone": "UTC",
            "start_time": start or "-",
            "end_time": end or "-",
            "duration": f"{duration_seconds // 3600:02d}:{duration_seconds % 3600 // 60:02d}:{duration_seconds % 60:02d}",
            "current": "00:00:00",
            "progress_percent": 0.0,
            "point_count": int(bounds.get("points") or 0),
            "quality": "good" if bounds.get("points") else "unavailable",
            "mock": False,
            "updated_at": utc_now(),
            "trace_id": get_trace_id(),
        }

    def fault_events(self, session_id: str) -> list[dict[str, Any]]:
        self.session_row(session_id)
        rows = self.state.database.query(
            "SELECT * FROM alarms WHERE session_id=? AND level>0 ORDER BY timestamp_utc", (session_id,)
        )
        return [
            {
                "id": f'fault-{row["id"]}',
                "label": f'{row["level_label"]}: {row["signal_name"]}',
                "time": row["timestamp_utc"],
                "level": row["level"],
                "can_id": row.get("can_id_hex"),
            }
            for row in rows
        ]

    def seek(self, session_id: str, progress_percent: float) -> dict[str, Any]:
        replay = self.replay(session_id)
        start, end = replay["start_time"], replay["end_time"]
        cursor = start
        if start != "-" and end != "-":
            start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
            cursor = (start_dt + (end_dt - start_dt) * (progress_percent / 100)).isoformat()
        return {**replay, "progress_percent": progress_percent, "cursor_time": cursor}

    def _expected_export_path(self, session_id: str, file_type: str) -> Path:
        extension = DOWNLOAD_TYPES[file_type][2]
        return self._session_export_dir(session_id) / f"{file_type}_{session_id}{extension}"

    def generate_download(self, session_id: str, file_type: str) -> Path:
        if file_type not in DOWNLOAD_TYPES:
            raise HTTPException(422, {"code": "INVALID_FILE_TYPE", "message": "不支持的历史文件类型", "details": {"file_type": file_type}})
        self.session_row(session_id)
        path = self._expected_export_path(session_id, file_type)
        if file_type == "raw-can":
            self._write_table_csv(
                path,
                "SELECT * FROM raw_can_frames WHERE session_id=? ORDER BY timestamp_utc",
                session_id,
            )
        elif file_type == "decoded-signals":
            self._write_table_csv(
                path,
                "SELECT * FROM decoded_signals WHERE session_id=? ORDER BY timestamp_utc",
                session_id,
            )
        elif file_type == "audit-log":
            rows = self.state.database.query(
                "SELECT * FROM operator_actions WHERE session_id=? ORDER BY timestamp_utc",
                (session_id,),
            )
            path.write_text(json.dumps({"session_id": session_id, "actions": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        elif file_type == "report-bundle":
            self._write_report_bundle(path, session_id)
        elif file_type == "curve-replay":
            self._write_replay_bundle(path, session_id)
        if not path.is_file():
            raise HTTPException(404, {"code": "SESSION_FILE_NOT_FOUND", "message": "会话没有可下载的数据", "details": {"session_id": session_id, "file_type": file_type}})
        return normalize_allowed_path(path, [self.export_root], expect_file=True)

    def _write_table_csv(self, path: Path, query: str, session_id: str) -> None:
        rows = self.state.database.query(query, (session_id,))
        if not rows:
            raise HTTPException(404, {"code": "SESSION_DATA_NOT_FOUND", "message": "会话没有对应数据", "details": {"session_id": session_id}})
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def _write_report_bundle(self, path: Path, session_id: str) -> None:
        reports = self.state.repositories.reports_for_session(session_id)
        if not reports:
            raise HTTPException(404, {"code": "REPORTS_NOT_FOUND", "message": "会话没有报告文件", "details": {"session_id": session_id}})
        manifest = []
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for row in reports:
                report_path = normalize_allowed_path(
                    row["file_path"],
                    [self.state.data_paths.reports, self.state.report_service.output_dir],
                    expect_file=True,
                )
                archive.write(report_path, arcname=report_path.name)
                manifest.append({"report_id": row["id"], "file_name": report_path.name, "sha256": sha256_file(report_path)})
            archive.writestr("manifest.json", json.dumps({"session_id": session_id, "files": manifest}, ensure_ascii=False, indent=2))

    def _write_replay_bundle(self, path: Path, session_id: str) -> None:
        signals = self.state.database.query(
            "SELECT * FROM decoded_signals WHERE session_id=? ORDER BY timestamp_utc", (session_id,)
        )
        if not signals:
            raise HTTPException(404, {"code": "REPLAY_DATA_NOT_FOUND", "message": "会话没有曲线回放数据", "details": {"session_id": session_id}})
        metadata = self.replay(session_id)
        alarms = self.state.database.query(
            "SELECT * FROM alarms WHERE session_id=? ORDER BY timestamp_utc", (session_id,)
        )
        csv_text = self._rows_to_csv(signals)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
            archive.writestr("signals.csv", "\ufeff" + csv_text)
            archive.writestr("alarms.json", json.dumps(alarms, ensure_ascii=False, indent=2))

    @staticmethod
    def _rows_to_csv(rows: list[dict[str, Any]]) -> str:
        from io import StringIO

        stream = StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue()

    def export_history(self, filters: dict[str, Any]) -> Path:
        items, _ = self.sessions(page=1, page_size=10000, **filters)
        path = self.export_root / f"history_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.csv"
        columns = ["session_id", "chassis_no", "vin", "serial_no", "started_at", "ended_at", "result", "failed_step", "operator", "station_id", "report_id"]
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows([{key: item.get(key) for key in columns} for item in items])
        return path

    def export_metadata(self, path: Path) -> dict[str, Any]:
        return {
            "file_name": path.name,
            "file_size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "download_url": f"/history/exports/{path.name}",
        }

    def history_export_path(self, file_id: str) -> Path:
        return normalize_allowed_path(self.export_root / file_id, [self.export_root], expect_file=True)
