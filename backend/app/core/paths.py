from __future__ import annotations
import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
CONFIG_DIR = Path(os.getenv("CHASSIS_CONFIG_DIR", PROJECT_ROOT / "configs"))
ASSETS_DIR = Path(os.getenv("CHASSIS_ASSETS_DIR", PROJECT_ROOT / "assets"))
DATA_DIR = Path(os.getenv("CHASSIS_DATA_DIR", PROJECT_ROOT / "data"))
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"
EXPORTS_DIR = DATA_DIR / "exports"
PRINT_JOBS_DIR = DATA_DIR / "print_jobs"
DB_PATH = DATA_DIR / "chassis_eol.db"

def ensure_data_dirs() -> None:
    for path in (DATA_DIR, REPORTS_DIR, LOGS_DIR, EXPORTS_DIR, PRINT_JOBS_DIR):
        path.mkdir(parents=True, exist_ok=True)
