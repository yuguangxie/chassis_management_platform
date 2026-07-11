from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import fitz
from docx import Document
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "docs" / "audit" / "evidence" / "simulation"
OUT = ROOT / "docs" / "audit" / "evidence" / "tests" / "report_validation.json"
SHOTS = ROOT / "docs" / "audit" / "evidence" / "screenshots" / "current"


def validate(profile: str) -> dict:
    result = json.loads((SIM / f"{profile}_eol_result.json").read_text(encoding="utf-8"))
    files = [ROOT / "data" / "reports" / name for name in result["new_report_files"]]
    by_suffix = {path.suffix: path for path in files}
    payload = json.loads(by_suffix[".json"].read_text(encoding="utf-8"))
    document = Document(by_suffix[".docx"])
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    reader = PdfReader(str(by_suffix[".pdf"]))
    pdf_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    rendered = fitz.open(by_suffix[".pdf"])
    page = rendered.load_page(0)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    screenshot = SHOTS / f"generated_{profile}_report_page1.png"
    pixmap.save(screenshot)
    rendered.close()
    session = payload.get("session", {})
    return {
        "profile": profile,
        "files": {suffix: {"path": str(path), "bytes": path.stat().st_size} for suffix, path in by_suffix.items()},
        "json_opened": True,
        "json_result": session.get("overall_result"),
        "json_has_software_version": bool(session.get("software_version")),
        "json_has_dbc_hash": bool(session.get("dbc_hash")),
        "json_has_config_version_or_hash": bool(session.get("config_version") or session.get("config_hash")),
        "json_has_operator": bool(session.get("operator")),
        "docx_opened": True,
        "docx_paragraph_count": len(paragraphs),
        "docx_paragraphs": paragraphs,
        "pdf_opened": True,
        "pdf_page_count": len(reader.pages),
        "pdf_extracted_text": pdf_text,
        "pdf_rendered_page": str(screenshot.relative_to(ROOT)).replace("\\", "/"),
    }


def main() -> int:
    results = [validate("normal_pass"), validate("bms_low_soc")]
    payload = {"audit_time": datetime.now().astimezone().isoformat(), "reports": results}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
