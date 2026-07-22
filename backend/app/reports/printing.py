from __future__ import annotations

from dataclasses import dataclass
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
from typing import Any, Protocol
import uuid

from app.core.time import utc_now
from app.security.auth import Principal
from app.storage.lifecycle import sha256_file


TERMINAL_PRINT_STATES = {"COMPLETED", "FAILED", "CANCELLED"}


@dataclass(frozen=True)
class PrinterInfo:
    name: str
    is_default: bool
    status: str = "available"


class PrintBackend(Protocol):
    name: str

    def printers(self) -> list[PrinterInfo]: ...
    def default_printer(self) -> str | None: ...
    def submit(self, path: Path, printer_name: str) -> str: ...
    def status(self, spooler_job_id: str, printer_name: str) -> tuple[str, str]: ...
    def cancel(self, spooler_job_id: str, printer_name: str) -> None: ...


class VirtualPrintBackend:
    """Deterministic spooler used only by test/mock profiles and CI."""

    name = "virtual"

    def __init__(self) -> None:
        self.jobs: dict[str, tuple[str, str]] = {}
        self._lock = threading.RLock()

    def printers(self) -> list[PrinterInfo]:
        return [PrinterInfo("Virtual PDF Printer", True)]

    def default_printer(self) -> str:
        return "Virtual PDF Printer"

    def submit(self, path: Path, printer_name: str) -> str:
        if not path.is_file() or path.suffix.lower() != ".pdf":
            raise RuntimeError("virtual spooler accepts an existing PDF only")
        job_id = "VIRTUAL-" + uuid.uuid4().hex[:12].upper()
        with self._lock:
            self.jobs[job_id] = ("QUEUED", "queued by virtual backend")
        return job_id

    def status(self, spooler_job_id: str, printer_name: str) -> tuple[str, str]:
        with self._lock:
            return self.jobs.get(spooler_job_id, ("FAILED", "virtual spooler job not found"))

    def cancel(self, spooler_job_id: str, printer_name: str) -> None:
        with self._lock:
            if spooler_job_id not in self.jobs:
                raise RuntimeError("virtual spooler job not found")
            state, _ = self.jobs[spooler_job_id]
            if state == "COMPLETED":
                raise RuntimeError("completed job cannot be cancelled")
            self.jobs[spooler_job_id] = ("CANCELLED", "cancelled")

    def set_status(self, spooler_job_id: str, status: str, detail: str = "") -> None:
        if status not in {"QUEUED", "PRINTING", "COMPLETED", "FAILED", "CANCELLED"}:
            raise ValueError(status)
        with self._lock:
            if spooler_job_id not in self.jobs:
                raise KeyError(spooler_job_id)
            self.jobs[spooler_job_id] = (status, detail)


class WindowsPrintBackend:
    """Windows RAW spooler adapter.

    The selected printer/driver must explicitly support PDF passthrough. Packaging
    validation reports a missing pywin32 dependency before production use.
    """

    name = "windows-spooler"

    @staticmethod
    def _module():
        if sys.platform != "win32":
            raise RuntimeError("Windows printing is only available on win32")
        try:
            import win32print  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("pywin32 is required for Windows spooler integration; install the production report extra") from exc
        return win32print

    def printers(self) -> list[PrinterInfo]:
        api = self._module()
        default = self.default_printer()
        flags = api.PRINTER_ENUM_LOCAL | api.PRINTER_ENUM_CONNECTIONS
        return [PrinterInfo(str(item[2]), str(item[2]) == default) for item in api.EnumPrinters(flags, None, 2)]

    def default_printer(self) -> str | None:
        api = self._module()
        try:
            return str(api.GetDefaultPrinter())
        except Exception:
            return None

    def submit(self, path: Path, printer_name: str) -> str:
        api = self._module()
        handle = api.OpenPrinter(printer_name)
        try:
            job_id = api.StartDocPrinter(handle, 1, (path.name, None, "RAW"))
            api.StartPagePrinter(handle)
            api.WritePrinter(handle, path.read_bytes())
            api.EndPagePrinter(handle)
            api.EndDocPrinter(handle)
            return str(job_id)
        finally:
            api.ClosePrinter(handle)

    def status(self, spooler_job_id: str, printer_name: str) -> tuple[str, str]:
        api = self._module()
        handle = api.OpenPrinter(printer_name)
        try:
            job = api.GetJob(handle, int(spooler_job_id), 1)
            flags = int(job.get("Status") or 0)
            detail = str(job.get("pStatus") or "")
            if flags & (api.JOB_STATUS_DELETING | api.JOB_STATUS_DELETED):
                return "CANCELLED", detail
            if flags & (api.JOB_STATUS_ERROR | api.JOB_STATUS_OFFLINE | api.JOB_STATUS_PAPEROUT | api.JOB_STATUS_BLOCKED_DEVQ):
                return "FAILED", detail or f"spooler status flags={flags}"
            if flags & api.JOB_STATUS_PRINTED:
                return "COMPLETED", detail
            if flags & api.JOB_STATUS_PRINTING:
                return "PRINTING", detail
            return "QUEUED", detail
        except Exception as exc:
            # Windows may remove a completed job immediately. GetJob failures are not
            # treated as success because that would create an unauditable false positive.
            return "FAILED", f"unable to query spooler job: {exc}"
        finally:
            api.ClosePrinter(handle)

    def cancel(self, spooler_job_id: str, printer_name: str) -> None:
        api = self._module()
        handle = api.OpenPrinter(printer_name)
        try:
            api.SetJob(handle, int(spooler_job_id), 0, None, api.JOB_CONTROL_CANCEL)
        finally:
            api.ClosePrinter(handle)


def build_print_backend(profile: str) -> PrintBackend:
    configured = os.getenv("CHASSIS_PRINT_BACKEND", "").strip().lower()
    if profile == "production" and configured == "virtual":
        raise RuntimeError("virtual print backend is forbidden in production")
    if configured == "virtual" or (not configured and profile in {"dev", "mock", "test"}):
        return VirtualPrintBackend()
    if configured in {"", "windows", "windows-spooler"}:
        return WindowsPrintBackend()
    raise RuntimeError(f"unsupported CHASSIS_PRINT_BACKEND={configured}")


class PrintService:
    def __init__(self, state: Any, backend: PrintBackend) -> None:
        self.state = state
        self.backend = backend
        self.task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self._monitor(), name="print-job-monitor")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None

    async def _monitor(self) -> None:
        while True:
            await asyncio.sleep(2.0)
            rows = self.state.database.query(
                "SELECT id FROM report_print_jobs WHERE status NOT IN ('COMPLETED','FAILED','CANCELLED') ORDER BY created_at LIMIT 100"
            )
            for row in rows:
                try:
                    self.job(str(row["id"]))
                except Exception:
                    # job() persists a fail-closed backend status where possible.
                    continue

    def printer_status(self) -> dict[str, Any]:
        try:
            printers = self.backend.printers()
            default = self.backend.default_printer()
            return {
                "backend": self.backend.name,
                "available": True,
                "default_printer": default,
                "printers": [item.__dict__ for item in printers],
                "error": None,
            }
        except Exception as exc:
            return {"backend": self.backend.name, "available": False, "default_printer": None, "printers": [], "error": str(exc)}

    def create(self, report_id: str, principal: Principal, *, preview_confirmed: bool, printer_name: str | None) -> dict[str, Any]:
        if not preview_confirmed:
            raise ValueError("PDF preview must be explicitly confirmed before printing")
        report = self.state.report_service.report_row(report_id)
        if report["report_type"] != "pdf":
            existing = self.state.report_service.find_session_report(report["session_id"], "pdf")
            if existing is None:
                generated = self.state.report_service.regenerate(report_id)
                pdf_id = next((item for item in generated["database_ids"] if item.endswith("-pdf")), None)
                if not pdf_id:
                    raise RuntimeError("PDF generation failed; printing was not submitted")
                report = self.state.report_service.report_row(pdf_id)
            else:
                report = self.state.report_service.report_row(existing["id"])
        path = Path(report["_path"])
        report_hash = sha256_file(path)
        selected = printer_name or self.state.config.printer_name or self.backend.default_printer()
        if not selected:
            raise RuntimeError("no printer is configured and the operating system has no default printer")
        available = {item.name for item in self.backend.printers()}
        if selected not in available:
            raise RuntimeError(f"configured printer is unavailable: {selected}")
        job_id = "PRINT-" + uuid.uuid4().hex[:12].upper()
        now = utc_now()
        database = self.state.database
        database.execute(
            "INSERT INTO report_print_jobs(id,report_id,file_path,requested_by,status,printer_name,backend,report_hash,attempts,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (job_id, report["id"], str(path), principal.username, "QUEUED", selected, self.backend.name, report_hash, 1, now, now),
        )
        self._audit(principal, "print_queued", job_id, {"report_id": report["id"], "report_hash": report_hash, "printer_name": selected})
        try:
            spooler_id = self.backend.submit(path, selected)
            database.execute(
                "UPDATE report_print_jobs SET spooler_job_id=?,status='QUEUED',status_detail=?,updated_at=? WHERE id=?",
                (spooler_id, "submitted to spooler", utc_now(), job_id),
            )
            self._audit(principal, "print_submitted", job_id, {"spooler_job_id": spooler_id, "printer_name": selected})
        except Exception as exc:
            database.execute(
                "UPDATE report_print_jobs SET status='FAILED',error_message=?,status_detail=?,updated_at=? WHERE id=?",
                (str(exc), str(exc), utc_now(), job_id),
            )
            self._audit(principal, "print_failed", job_id, {"error": str(exc), "report_hash": report_hash}, result="FAILED")
            raise
        return self.job(job_id, refresh=False)

    def job(self, job_id: str, *, refresh: bool = True) -> dict[str, Any]:
        row = self.state.database.query_one("SELECT * FROM report_print_jobs WHERE id=?", (job_id,))
        if row is None:
            raise KeyError(job_id)
        if refresh and row["status"] not in TERMINAL_PRINT_STATES and row.get("spooler_job_id"):
            previous = str(row["status"])
            status, detail = self.backend.status(str(row["spooler_job_id"]), str(row["printer_name"]))
            completed_at = utc_now() if status == "COMPLETED" else row.get("completed_at")
            cancelled_at = utc_now() if status == "CANCELLED" else row.get("cancelled_at")
            self.state.database.execute(
                "UPDATE report_print_jobs SET status=?,status_detail=?,completed_at=?,cancelled_at=?,updated_at=? WHERE id=?",
                (status, detail, completed_at, cancelled_at, utc_now(), job_id),
            )
            row = self.state.database.query_one("SELECT * FROM report_print_jobs WHERE id=?", (job_id,)) or row
            if status != previous:
                self.state.database.execute(
                    "INSERT INTO operator_actions(timestamp_utc,operator,role,action_type,target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        utc_now(), str(row["requested_by"]), "operator", "print_status_changed", job_id,
                        json.dumps({"from": previous, "to": status, "detail": detail, "report_hash": row.get("report_hash")}, ensure_ascii=False),
                        status, "",
                    ),
                )
        return {**row, "job_id": row["id"]}

    def cancel(self, job_id: str, principal: Principal) -> dict[str, Any]:
        row = self.job(job_id)
        if row["status"] in TERMINAL_PRINT_STATES:
            raise RuntimeError(f"print job is already terminal: {row['status']}")
        self.backend.cancel(str(row["spooler_job_id"]), str(row["printer_name"]))
        now = utc_now()
        self.state.database.execute(
            "UPDATE report_print_jobs SET status='CANCELLED',status_detail='cancelled by operator',cancelled_at=?,updated_at=? WHERE id=?",
            (now, now, job_id),
        )
        self._audit(principal, "print_cancelled", job_id, {"report_hash": row.get("report_hash")})
        return self.job(job_id, refresh=False)

    def retry(self, job_id: str, principal: Principal) -> dict[str, Any]:
        row = self.job(job_id)
        if row["status"] not in {"FAILED", "CANCELLED"}:
            raise RuntimeError("only failed or cancelled print jobs can be retried")
        path = Path(row["file_path"])
        current_hash = sha256_file(path)
        if current_hash != row["report_hash"]:
            raise RuntimeError("report file changed after the original print request")
        spooler_id = self.backend.submit(path, str(row["printer_name"]))
        self.state.database.execute(
            "UPDATE report_print_jobs SET status='QUEUED',spooler_job_id=?,attempts=attempts+1,error_message=NULL,status_detail='retry submitted',cancelled_at=NULL,completed_at=NULL,updated_at=? WHERE id=?",
            (spooler_id, utc_now(), job_id),
        )
        self._audit(principal, "print_retried", job_id, {"spooler_job_id": spooler_id, "report_hash": current_hash})
        return self.job(job_id, refresh=False)

    def _audit(self, principal: Principal, action: str, target: str, payload: dict[str, Any], result: str = "OK") -> None:
        self.state.database.execute(
            "INSERT INTO operator_actions(timestamp_utc,operator,role,action_type,target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?)",
            (utc_now(), principal.username, principal.role.value, action, target, json.dumps(payload, ensure_ascii=False, default=str), result, ""),
        )
