from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "chassis_eol.db"
OUT = ROOT / "docs" / "audit" / "evidence" / "tests" / "database_audit.json"
EXPECTED = [
    "test_sessions",
    "test_steps",
    "test_assertions",
    "raw_can_frames",
    "decoded_signals",
    "signal_statistics",
    "alarms",
    "reports",
    "operator_actions",
    "config_history",
    "software_versions",
]


def main() -> int:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    try:
        table_names = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        tables = {}
        for name in EXPECTED:
            if name not in table_names:
                tables[name] = {"exists": False}
                continue
            columns = [dict(row) for row in connection.execute(f"PRAGMA table_info({name})")]
            indexes = [dict(row) for row in connection.execute(f"PRAGMA index_list({name})")]
            foreign_keys = [dict(row) for row in connection.execute(f"PRAGMA foreign_key_list({name})")]
            count = int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
            tables[name] = {
                "exists": True,
                "row_count": count,
                "columns": columns,
                "indexes": indexes,
                "foreign_keys": foreign_keys,
            }
        result = {
            "audit_time": datetime.now().astimezone().isoformat(),
            "database_path": str(DB),
            "database_bytes": DB.stat().st_size,
            "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
            "foreign_keys_enabled": bool(connection.execute("PRAGMA foreign_keys").fetchone()[0]),
            "integrity_check": connection.execute("PRAGMA integrity_check").fetchone()[0],
            "busy_timeout_ms": int(connection.execute("PRAGMA busy_timeout").fetchone()[0]),
            "all_tables": table_names,
            "expected_tables_present": sum(1 for name in EXPECTED if name in table_names),
            "expected_table_count": len(EXPECTED),
            "tables": tables,
            "files": {
                "wal": {"exists": DB.with_name(DB.name + "-wal").exists(), "bytes": DB.with_name(DB.name + "-wal").stat().st_size if DB.with_name(DB.name + "-wal").exists() else 0},
                "shm": {"exists": DB.with_name(DB.name + "-shm").exists(), "bytes": DB.with_name(DB.name + "-shm").stat().st_size if DB.with_name(DB.name + "-shm").exists() else 0},
                "raw_can_csv": {"exists": (ROOT / "data/logs/raw_can_current.csv").exists(), "bytes": (ROOT / "data/logs/raw_can_current.csv").stat().st_size if (ROOT / "data/logs/raw_can_current.csv").exists() else 0},
            },
            "report_file_counts": {
                suffix: len(list((ROOT / "data/reports").glob(f"*{suffix}"))) for suffix in (".json", ".docx", ".pdf", ".csv")
            },
        }
    finally:
        connection.close()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "journal_mode": result["journal_mode"],
        "integrity_check": result["integrity_check"],
        "tables_present": f'{result["expected_tables_present"]}/{result["expected_table_count"]}',
        "row_counts": {name: info.get("row_count") for name, info in tables.items()},
        "raw_can_csv_mb": round(result["files"]["raw_can_csv"]["bytes"] / 1024 / 1024, 2),
        "report_file_counts": result["report_file_counts"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
