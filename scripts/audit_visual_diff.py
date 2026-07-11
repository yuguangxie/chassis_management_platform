from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageStat


ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs" / "audit" / "evidence" / "screenshots" / "current"
REFERENCE = ROOT / "docs" / "audit" / "evidence" / "screenshots" / "reference"
DIFF = ROOT / "docs" / "audit" / "evidence" / "screenshots" / "diff"


def main() -> int:
    DIFF.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for reference_path in sorted(REFERENCE.glob("*.png")):
        key = reference_path.stem
        current_path = CURRENT / f"{key}_1920x1080.png"
        if not current_path.exists():
            rows.append({"page": key, "status": "missing_current"})
            continue
        reference = Image.open(reference_path).convert("RGB")
        current = Image.open(current_path).convert("RGB")
        original_size = current.size
        if current.size != reference.size:
            current = current.resize(reference.size, Image.Resampling.LANCZOS)
        delta = ImageChops.difference(reference, current)
        stat = ImageStat.Stat(delta)
        mean_abs = sum(stat.mean) / 3.0
        rms = math.sqrt(sum(value * value for value in stat.rms) / 3.0)
        gray = delta.convert("L")
        histogram = gray.histogram()
        pixels = reference.width * reference.height
        changed_10 = sum(histogram[11:]) / pixels * 100
        changed_30 = sum(histogram[31:]) / pixels * 100

        amplified = ImageEnhance.Contrast(delta).enhance(2.2)
        canvas = Image.new("RGB", (reference.width * 3, reference.height), "black")
        canvas.paste(reference, (0, 0))
        canvas.paste(current, (reference.width, 0))
        canvas.paste(amplified, (reference.width * 2, 0))
        canvas.save(DIFF / f"{key}_reference_current_diff.png", optimize=True)
        delta.save(DIFF / f"{key}_absolute_diff.png", optimize=True)
        rows.append(
            {
                "page": key,
                "status": "compared",
                "reference_width": reference.width,
                "reference_height": reference.height,
                "current_width": original_size[0],
                "current_height": original_size[1],
                "mean_absolute_difference_0_255": round(mean_abs, 3),
                "rms_difference_0_255": round(rms, 3),
                "pixels_changed_over_10_percent": round(changed_10, 3),
                "pixels_changed_over_30_percent": round(changed_30, 3),
                "composite": f"evidence/screenshots/diff/{key}_reference_current_diff.png",
            }
        )
    payload = {"generated_at": datetime.now().astimezone().isoformat(), "method": "Pillow RGB absolute pixel difference; layout shifts and text anti-aliasing both contribute", "pages": rows}
    (DIFF / "visual_diff_metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if rows:
        with (DIFF / "visual_diff_metrics.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if all(row.get("status") == "compared" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
