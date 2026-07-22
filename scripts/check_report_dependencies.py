from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.reports.dependencies import report_dependency_status


if __name__ == "__main__":
    status = report_dependency_status(ROOT / "configs" / "report_config.yaml")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    raise SystemExit(0 if status["ready"] else 1)
