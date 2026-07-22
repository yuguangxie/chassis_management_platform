from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import sys
from typing import Any

import yaml


def report_dependency_status(config_path: Path) -> dict[str, Any]:
    document = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    report = (document or {}).get("report", {})
    renderer = str(report.get("pdf_renderer") or "reportlab-native").lower()
    converter = str(report.get("docx_to_pdf_converter") or "disabled").lower()
    python_docx = importlib.util.find_spec("docx") is not None
    reportlab = importlib.util.find_spec("reportlab") is not None
    fitz = importlib.util.find_spec("fitz") is not None
    converter_available = True
    converter_path: str | None = None
    action = "none"
    if converter == "libreoffice":
        converter_path = shutil.which("soffice") or shutil.which("libreoffice")
        converter_available = converter_path is not None
        action = "Install LibreOffice and include soffice in PATH, or set an explicit packaged executable path."
    elif converter == "word":
        converter_available = sys.platform == "win32" and importlib.util.find_spec("win32com") is not None
        action = "Install Microsoft Word and pywin32 in the packaged Windows runtime."
    elif converter != "disabled":
        converter_available = False
        action = f"Unsupported docx_to_pdf_converter: {converter}"
    renderer_available = renderer == "reportlab-native" and reportlab
    if renderer != "reportlab-native":
        renderer_available = False
        action = f"Unsupported pdf_renderer: {renderer}"
    ready = python_docx and fitz and renderer_available and converter_available
    return {
        "ready": ready,
        "pdf_renderer": renderer,
        "pdf_renderer_available": renderer_available,
        "docx_to_pdf_converter": converter,
        "docx_to_pdf_available": converter_available,
        "converter_path": converter_path,
        "python_docx_available": python_docx,
        "pdf_preview_available": fitz,
        "action": None if ready else action or "Install missing report runtime dependencies.",
        "semantics": (
            "PDF and DOCX are independently rendered; no DOCX file is renamed or presented as PDF."
            if converter == "disabled"
            else "Configured DOCX-to-PDF conversion dependency must pass packaging validation before use."
        ),
    }
