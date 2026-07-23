from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.paths import PROJECT_ROOT


class ReleaseMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool = False
    software_version: str | None = None
    commit: str | None = None
    built_at_utc: str | None = None
    release_label: str = "unavailable"
    signed: bool = False
    formal_release: bool = False
    dirty: bool | None = None
    manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    manifest_path: str | None = None
    error: str | None = None


def release_manifest_path() -> Path | None:
    configured = os.getenv("CHASSIS_RELEASE_MANIFEST", "").strip()
    candidates = [
        Path(configured) if configured else None,
        PROJECT_ROOT / "desktop" / "release-build.json",
        PROJECT_ROOT / "desktop" / "release" / "windows" / "release-manifest.json",
    ]
    return next((path.resolve(strict=False) for path in candidates if path and path.is_file()), None)


def load_release_metadata() -> ReleaseMetadata:
    path = release_manifest_path()
    if path is None:
        return ReleaseMetadata(error="release manifest is unavailable")
    try:
        raw = path.read_bytes()
        payload: dict[str, Any] = json.loads(raw.decode("utf-8"))
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        signing = payload.get("signing") if isinstance(payload.get("signing"), dict) else {}
        signed = bool(signing.get("signed", payload.get("signed", False)))
        formal = bool(signing.get("formal_release", signed and not source.get("dirty", payload.get("source_dirty", True))))
        return ReleaseMetadata(
            available=True,
            software_version=str(payload.get("software_version") or payload.get("version") or "") or None,
            commit=str(payload.get("commit") or source.get("commit") or "") or None,
            built_at_utc=str(payload.get("built_at_utc") or payload.get("built_at") or "") or None,
            release_label=str(payload.get("release_label") or "unavailable"),
            signed=signed,
            formal_release=formal,
            dirty=bool(source.get("dirty", payload.get("source_dirty")))
            if "dirty" in source or "source_dirty" in payload
            else None,
            manifest_sha256=hashlib.sha256(raw).hexdigest(),
            manifest_path=str(path),
        )
    except Exception as exc:
        return ReleaseMetadata(
            manifest_path=str(path),
            error=f"invalid release manifest: {type(exc).__name__}: {exc}",
        )
