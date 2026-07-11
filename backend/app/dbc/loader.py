from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
from app.core.paths import ASSETS_DIR

@dataclass
class DbcLoadResult:
    loaded: bool
    raw_only: bool
    file: str | None
    hash: str | None
    version: str
    error: str | None
    database: object | None = None

class DbcLoader:
    def __init__(self, assets_dir: Path = ASSETS_DIR) -> None:
        self.assets_dir = assets_dir

    def scan(self) -> list[Path]:
        return sorted(self.assets_dir.glob("*.dbc"), key=lambda p: p.stat().st_mtime, reverse=True)

    def load(self) -> DbcLoadResult:
        files = self.scan()
        if not files:
            return DbcLoadResult(False, True, None, None, "raw-only", "no dbc found")
        path = files[0]
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()[:16]
        try:
            import cantools
            db = cantools.database.load_file(str(path), strict=False)
            version = getattr(db, "version", None) or path.stem
            return DbcLoadResult(True, False, str(path), digest, version, None, db)
        except Exception as exc:
            return DbcLoadResult(False, True, str(path), digest, "raw-only", str(exc))
