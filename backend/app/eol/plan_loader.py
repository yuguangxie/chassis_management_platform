from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.paths import CONFIG_DIR
from app.eol.models import TestPlanDocument


class PlanLoadError(RuntimeError):
    pass


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PlanLoadError(f"failed to read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlanLoadError(f"{path} must contain a YAML mapping")
    return payload


def load_test_plan(path: Path | None = None) -> TestPlanDocument:
    plan_path = path or CONFIG_DIR / "test_plan.yaml"
    try:
        return TestPlanDocument.model_validate(_read_yaml(plan_path))
    except Exception as exc:
        raise PlanLoadError(f"invalid EOL test plan {plan_path}: {exc}") from exc


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    return _read_yaml(path or CONFIG_DIR / "thresholds.yaml")


def resolve_threshold(thresholds: dict[str, Any], reference: str | None) -> Any:
    if not reference:
        return None
    current: Any = thresholds
    for part in reference.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(f"threshold reference not found: {reference}")
        current = current[part]
    return current
