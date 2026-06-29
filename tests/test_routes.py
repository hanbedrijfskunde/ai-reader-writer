from fastapi.testclient import TestClient
from app.main import create_app


def test_health_endpoint(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def _client(tmp_path, monkeypatch):
    from app.config import load_settings
    import app.main as main

    settings = load_settings(env_file=tmp_path / "none.env", data_dir=tmp_path / "data")
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    return TestClient(main.create_app())


def test_index_renders(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Reader" in resp.text


def test_add_video_lists_source(tmp_path, monkeypatch):
    import app.main as main
    fake = {
        "metadata": {"title": "Mijn video", "url": "https://youtu.be/x",
                     "video_id": "x", "channel": "C", "duration": "1:00",
                     "thumbnail": "https://t/thumb.jpg"},
        "transcript": [{"ts": "0:00", "text": "hallo wereld"}],
    }
    monkeypatch.setattr(main.video, "fetch_raw", lambda url, _runner=None: fake)
    monkeypatch.setattr(main, "summarize", lambda text, **kw: "Synopsis.")
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/sources/video", data={"url": "https://youtu.be/x"})
    assert resp.status_code == 200
    assert "Mijn video" in resp.text


def test_add_pdf_lists_source(tmp_path, monkeypatch, sample_pdf_dir):
    import pytest
    pdf_file = sample_pdf_dir / "Over leiderschap_DIG.pdf"
    if not pdf_file.exists():
        pytest.skip("sample PDF ontbreekt")
    client = _client(tmp_path, monkeypatch)
    with pdf_file.open("rb") as fh:
        resp = client.post(
            "/sources/pdf",
            files={"file": ("Over leiderschap_DIG.pdf", fh, "application/pdf")},
        )
    assert resp.status_code == 200
    assert "Over leiderschap" in resp.text


def test_pdf_upload_filename_is_sanitized(tmp_path, monkeypatch, sample_pdf_dir):
    import pytest
    pdf_file = sample_pdf_dir / "Over leiderschap_DIG.pdf"
    if not pdf_file.exists():
        pytest.skip("sample PDF ontbreekt")
    client = _client(tmp_path, monkeypatch)
    with pdf_file.open("rb") as fh:
        resp = client.post("/sources/pdf",
            files={"file": ("../../evil.pdf", fh, "application/pdf")})
    assert resp.status_code == 200
    # the file must land inside data/uploads as evil.pdf, not above it
    uploads = tmp_path / "data" / "uploads"
    assert (uploads / "evil.pdf").exists()
    assert not (tmp_path / "evil.pdf").exists()


def test_export_writes_reader_html(tmp_path, monkeypatch, sample_pdf_dir):
    import pytest
    from pathlib import Path
    pdf_file = sample_pdf_dir / "Over leiderschap_DIG.pdf"
    if not pdf_file.exists():
        pytest.skip("sample PDF ontbreekt")
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    with pdf_file.open("rb") as fh:
        client.post("/sources/pdf", files={"file": ("doc.pdf", fh, "application/pdf")})
    def fake_render(src_path, out_dir, dpi=144):
        out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / "page-0001.png"; p.write_bytes(b"\x89PNG\r\n")
        return [p]
    monkeypatch.setattr(main.pdf, "render_pages_to_png", fake_render)
    resp = client.post("/export")
    assert resp.status_code == 200
    render_dir = tmp_path / "data" / "renders"
    assert (render_dir / "index.html").exists()
    assert "page-0001.png" in (render_dir / "index.html").read_text(encoding="utf-8")


def test_video_rejects_non_http_url(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/sources/video", data={"url": "javascript:alert(1)"})
    assert resp.status_code == 400


def test_meta_saved_prefilled_and_used_in_export(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/meta", data={"reader_title": "Strategie",
                                       "module_code": "BK-101",
                                       "academic_year": "2025-2026"})
    assert resp.status_code == 200
    # index prefilled with the saved values
    idx = client.get("/").text
    assert "Strategie" in idx and "BK-101" in idx and "2025-2026" in idx
    # export uses reader_title as <h1> and module/year as subtitle
    monkeypatch.setattr(main.pdf, "render_pages_to_png", lambda *a, **k: [])
    exp = client.post("/export")
    assert exp.status_code == 200
    html_txt = (tmp_path / "data" / "renders" / "index.html").read_text(encoding="utf-8")
    assert "<h1>Strategie</h1>" in html_txt
    assert "BK-101 · 2025-2026" in html_txt


def _add_transcriptless_video(client, monkeypatch):
    """Add a video via the route with NO transcript; return its source id."""
    import re
    import app.main as main
    fake = {
        "metadata": {"title": "Lange talk", "url": "https://youtu.be/z",
                     "video_id": "z", "thumbnail": "https://t/thumb.jpg"},
        "transcript": [],
    }
    monkeypatch.setattr(main.video, "fetch_raw", lambda url, _runner=None: fake)
    partial = client.post("/sources/video", data={"url": "https://youtu.be/z"}).text
    return int(re.search(r'data-id="(\d+)"', partial).group(1))


def test_video_synopsis_can_be_edited_and_exported(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    sid = _add_transcriptless_video(client, monkeypatch)
    # teacher fills in a manual synopsis directly
    resp = client.post(f"/sources/{sid}/content",
                       data={"synopsis": "Handmatige samenvatting."})
    assert resp.status_code == 200
    monkeypatch.setattr(main.pdf, "render_pages_to_png", lambda *a, **k: [])
    client.post("/export")
    html_txt = (tmp_path / "data" / "renders" / "index.html").read_text(encoding="utf-8")
    assert "Handmatige samenvatting." in html_txt


def test_pasted_transcript_generates_synopsis(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    sid = _add_transcriptless_video(client, monkeypatch)
    # AI is mocked: pasting a transcript should trigger summarize and store it
    monkeypatch.setattr(main, "summarize", lambda text, **kw: "AI-synopsis uit transcript.")
    resp = client.post(f"/sources/{sid}/content",
                       data={"transcript": "het volledige transcript hier"})
    assert resp.status_code == 200
    monkeypatch.setattr(main.pdf, "render_pages_to_png", lambda *a, **k: [])
    client.post("/export")
    html_txt = (tmp_path / "data" / "renders" / "index.html").read_text(encoding="utf-8")
    assert "AI-synopsis uit transcript." in html_txt
