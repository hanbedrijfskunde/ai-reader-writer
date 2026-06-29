from __future__ import annotations

from pathlib import Path


def html_to_pdf(html_path: Path, pdf_path: Path) -> Path:
    """Render an on-disk HTML file to PDF using headless Chromium.

    Reuses the Playwright/Chromium install already required for YouTube
    transcript fetching. A4, print backgrounds on.
    """
    from playwright.sync_api import sync_playwright

    html_path = Path(html_path)
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            page.pdf(path=str(pdf_path), format="A4", print_background=True)
        finally:
            browser.close()
    return pdf_path
