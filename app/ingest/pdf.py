from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def page_count(pdf_path: Path) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def extract_text(pdf_path: Path) -> str:
    parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n\n".join(parts).strip()


def has_text_layer(pdf_path: Path) -> bool:
    with fitz.open(pdf_path) as doc:
        for page in doc:
            if page.get_text("text").strip():
                return True
    return False


def render_pages_to_png(pdf_path: Path, out_dir: Path, dpi: int = 144) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            out = out_dir / f"page-{i:04d}.png"
            pix.save(out)
            out_paths.append(out)
    return out_paths
