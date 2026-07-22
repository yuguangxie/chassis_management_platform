from pathlib import Path
import sys

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import load_config


runtime = load_config()
uvicorn.run("app.main:app", host=runtime.host, port=runtime.port, reload=False, app_dir=str(ROOT / "backend"))
