from __future__ import annotations

import json
import math
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageStat


ROOT = Path(__file__).resolve().parents[1]
CURRENT = Path(os.environ.get("PHASE04_CURRENT_DIR", ROOT / "docs" / "verification" / "phase-04" / "screenshots" / "current"))
REFERENCE = ROOT / "docs" / "verification" / "phase-04" / "screenshots" / "reference"
DIFF = Path(os.environ.get("PHASE04_DIFF_DIR", ROOT / "docs" / "verification" / "phase-04" / "screenshots" / "diff"))


def main() -> int:
    DIFF.mkdir(parents=True, exist_ok=True)
    rows = []
    for reference_path in sorted(REFERENCE.glob("*.png")):
        page = reference_path.stem
        current_path = CURRENT / f"{page}_1920x1080.png"
        if not current_path.exists():
            rows.append({"page": page, "status": "missing_current"})
            continue
        reference = Image.open(reference_path).convert("RGB")
        current_original = Image.open(current_path).convert("RGB")
        current = current_original.resize(reference.size, Image.Resampling.LANCZOS)
        delta = ImageChops.difference(reference, current)
        stats = ImageStat.Stat(delta)
        mean_abs = sum(stats.mean) / 3
        rms = math.sqrt(sum(value * value for value in stats.rms) / 3)
        amplified = ImageEnhance.Contrast(delta).enhance(2.2)
        composite = Image.new("RGB", (reference.width * 3, reference.height))
        composite.paste(reference, (0, 0))
        composite.paste(current, (reference.width, 0))
        composite.paste(amplified, (reference.width * 2, 0))
        composite_path = DIFF / f"{page}_reference_current_diff.png"
        composite.save(composite_path, optimize=True)
        delta.save(DIFF / f"{page}_absolute_diff.png", optimize=True)
        rows.append(
            {
                "page": page,
                "status": "compared",
                "reference_size": reference.size,
                "current_size": current_original.size,
                "mean_absolute_difference_0_255": round(mean_abs, 3),
                "rms_difference_0_255": round(rms, 3),
                "composite": str(composite_path.relative_to(ROOT)),
            }
        )
    payload = {
        "method": "Pillow RGB absolute difference. The metric includes text, live data, and anti-aliasing differences; it is evidence, not a pass/fail score.",
        "pages": rows,
        "system_settings": "No reliable reference image was supplied; evaluated against the shared UI style guide and page specification.",
    }
    (DIFF / "visual_diff_metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
