from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Iterable

from fastapi import HTTPException


SAFE_FILE_ID = re.compile(r"^[A-Za-z0-9._-]{1,180}$")


def normalize_allowed_path(
    value: str | Path,
    roots: Iterable[Path],
    *,
    must_exist: bool = True,
    expect_file: bool | None = None,
) -> Path:
    candidate = Path(value).expanduser().resolve(strict=False)
    allowed = [Path(root).expanduser().resolve(strict=False) for root in roots]
    if not any(candidate == root or root in candidate.parents for root in allowed):
        raise HTTPException(
            403,
            {
                "code": "PATH_OUTSIDE_ALLOWED_ROOT",
                "message": "文件路径不在允许目录内",
                "details": {"path": str(candidate)},
            },
        )
    if must_exist and not candidate.exists():
        raise HTTPException(
            404,
            {
                "code": "FILE_NOT_FOUND",
                "message": "文件不存在",
                "details": {"path": str(candidate)},
            },
        )
    if expect_file is True and candidate.exists() and not candidate.is_file():
        raise HTTPException(
            422,
            {
                "code": "FILE_REQUIRED",
                "message": "目标不是文件",
                "details": {"path": str(candidate)},
            },
        )
    if expect_file is False and candidate.exists() and not candidate.is_dir():
        raise HTTPException(
            422,
            {
                "code": "DIRECTORY_REQUIRED",
                "message": "目标不是目录",
                "details": {"path": str(candidate)},
            },
        )
    return candidate


def validate_file_id(value: str) -> str:
    if not SAFE_FILE_ID.fullmatch(value) or value in {".", ".."}:
        raise HTTPException(
            422,
            {
                "code": "INVALID_FILE_ID",
                "message": "文件标识不合法",
                "details": {"file_id": value},
            },
        )
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def human_size(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} GB"
