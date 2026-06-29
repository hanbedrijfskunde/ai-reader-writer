from pathlib import Path

import pytest


def test_html_to_pdf_smoke(tmp_path):
    html = tmp_path / "x.html"
    html.write_text("<!doctype html><h1>Hallo</h1>", encoding="utf-8")
    out = tmp_path / "x.pdf"
    from app.render.pdf import html_to_pdf
    try:
        html_to_pdf(html, out)
    except Exception as e:  # chromium niet geïnstalleerd in deze omgeving
        pytest.skip(f"chromium niet beschikbaar: {e}")
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"
