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
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "")
    client = _client(tmp_path, monkeypatch)
    client.post("/sources/video", data={"url": "https://youtu.be/x"})
    # background finished -> the real title now shows in a fresh render
    assert "Mijn video" in client.get("/").text


def test_add_video_returns_pending_and_schedules(tmp_path, monkeypatch):
    import re
    import app.main as main
    scheduled = {}

    def fake_process(store, settings, source_id, url):
        scheduled["id"] = source_id
        scheduled["url"] = url  # do NOT process -> source stays pending

    monkeypatch.setattr(main, "process_video", fake_process)
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/sources/video", data={"url": "https://youtu.be/x"})
    assert resp.status_code == 200
    assert "Video wordt opgehaald" in resp.text          # placeholder shown
    sid = int(re.search(r'data-id="(\d+)"', resp.text).group(1))
    assert scheduled == {"id": sid, "url": "https://youtu.be/x"}
    # the source exists and is still processing (background was a no-op)
    src = {s.id: s for s in main_store(client).list_sources(store_project_id(client))}[sid]
    assert src.processing is True


def test_sources_poll_route_returns_list(tmp_path, monkeypatch):
    monkeypatch.setattr(__import__("app.main", fromlist=["x"]), "process_video",
                        lambda *a, **k: None)
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/sources")
    assert resp.status_code == 200
    assert 'id="source-list"' in resp.text


def test_add_pdf_lists_source(tmp_path, monkeypatch, sample_pdf_dir):
    import pytest
    import app.main as main
    pdf_file = sample_pdf_dir / "Over leiderschap_DIG.pdf"
    if not pdf_file.exists():
        pytest.skip("sample PDF ontbreekt")
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "")
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
    import app.main as main
    pdf_file = sample_pdf_dir / "Over leiderschap_DIG.pdf"
    if not pdf_file.exists():
        pytest.skip("sample PDF ontbreekt")
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "")
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
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "")
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


def _add_pdf_like_source(client, monkeypatch):
    """Add a source that has text (via the video route with a transcript), so
    question generation has something to work with. Returns its source id."""
    import re
    import app.main as main
    fake = {
        "metadata": {"title": "Bron", "url": "https://youtu.be/q",
                     "video_id": "q", "thumbnail": "https://t/t.jpg"},
        "transcript": [{"ts": "0:00", "text": "inhoud over leiderschap"}],
    }
    monkeypatch.setattr(main.video, "fetch_raw", lambda url, _runner=None: fake)
    monkeypatch.setattr(main, "summarize", lambda text, **kw: "syn")
    partial = client.post("/sources/video", data={"url": "https://youtu.be/q"}).text
    return int(re.search(r'data-id="(\d+)"', partial).group(1))


def test_generate_questions_route(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "")
    sid = _add_pdf_like_source(client, monkeypatch)
    monkeypatch.setattr(main, "generate_questions",
                        lambda text, level, n=3, **kw: ["V1?", "V2?", "V3?"])
    resp = client.post(f"/sources/{sid}/questions/generate")
    assert resp.status_code == 200
    assert "V1?" in resp.text and "V3?" in resp.text


def test_generate_questions_skipped_without_text(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    sid = _add_transcriptless_video(client, monkeypatch)  # text == ""
    called = {"n": 0}

    def spy(*a, **k):
        called["n"] += 1
        return ["x"]

    monkeypatch.setattr(main, "generate_questions", spy)
    resp = client.post(f"/sources/{sid}/questions/generate")
    assert resp.status_code == 200
    assert called["n"] == 0  # no source text -> generator not called


def test_add_edit_delete_question(tmp_path, monkeypatch):
    import re
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "")
    sid = _add_pdf_like_source(client, monkeypatch)
    r1 = client.post(f"/sources/{sid}/questions/add", data={"text": "Mijn vraag?"})
    assert "Mijn vraag?" in r1.text
    qid = int(re.search(r'/questions/(\d+)/edit', r1.text).group(1))
    r2 = client.post(f"/questions/{qid}/edit", data={"text": "Aangepast?"})
    assert "Aangepast?" in r2.text and "Mijn vraag?" not in r2.text
    r3 = client.post(f"/questions/{qid}/delete")
    assert "Aangepast?" not in r3.text


def test_export_html_includes_questions(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "")
    sid = _add_pdf_like_source(client, monkeypatch)
    client.post(f"/sources/{sid}/questions/add", data={"text": "Exportvraag?"})
    monkeypatch.setattr(main.pdf, "render_pages_to_png", lambda *a, **k: [])
    client.post("/export")
    html_txt = (tmp_path / "data" / "renders" / "index.html").read_text(encoding="utf-8")
    assert "Verdiepende vragen" in html_txt
    assert "Exportvraag?" in html_txt


def test_export_pdf_route_invokes_printer(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "")
    sid = _add_pdf_like_source(client, monkeypatch)
    monkeypatch.setattr(main.pdf, "render_pages_to_png", lambda *a, **k: [])
    seen = {}

    def fake_pdf(html_path, pdf_path):
        from pathlib import Path
        Path(pdf_path).write_bytes(b"%PDF-1.4 fake")
        seen["html"] = str(html_path)
        seen["pdf"] = str(pdf_path)
        return Path(pdf_path)

    monkeypatch.setattr(main, "html_to_pdf", fake_pdf)
    resp = client.post("/export/pdf")
    assert resp.status_code == 200
    assert seen["html"].endswith("index.html")
    assert (tmp_path / "data" / "renders" / "reader.pdf").exists()


def test_question_text_escaped_in_editor(tmp_path, monkeypatch):
    import re
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "")
    sid = _add_pdf_like_source(client, monkeypatch)
    resp = client.post(f"/sources/{sid}/questions/add",
                       data={"text": '<b>"gevaar"</b>'})
    assert resp.status_code == 200
    # the raw tag must not appear unescaped; the escaped form must
    assert "<b>\"gevaar\"</b>" not in resp.text
    assert "&lt;b&gt;" in resp.text


def test_adding_video_with_text_extracts_quote(tmp_path, monkeypatch):
    import re
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "inhoud over leiderschap")
    sid = _add_pdf_like_source(client, monkeypatch)  # this source has transcript text
    store = main_store(client)
    src = {s.id: s for s in store.list_sources(store_project_id(client))}[sid]
    assert src.quote == "inhoud over leiderschap"


def test_adding_source_without_text_skips_quote(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    called = {"n": 0}
    def spy(text, **kw):
        called["n"] += 1
        return "x"
    monkeypatch.setattr(main, "extract_quote", spy)
    _add_transcriptless_video(client, monkeypatch)  # text == ""
    assert called["n"] == 0


def main_store(client):
    return client.app.state.store


def store_project_id(client):
    return client.app.state.project_id


def test_export_html_includes_quote(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "inhoud over leiderschap")
    sid = _add_pdf_like_source(client, monkeypatch)  # has text -> quote stored
    monkeypatch.setattr(main.pdf, "render_pages_to_png", lambda *a, **k: [])
    client.post("/export")
    html_txt = (tmp_path / "data" / "renders" / "index.html").read_text(encoding="utf-8")
    assert 'class="r-quote"' in html_txt
    assert "inhoud over leiderschap" in html_txt


def test_index_uses_design_system(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    body = client.get("/").text
    assert "fonts.googleapis.com" in body
    assert "#e5007d" in body          # magenta accent token
    assert "Archivo" in body
    # existing functionality still present
    assert 'hx-post="/sources/pdf"' in body
    assert 'hx-post="/export/pdf"' in body


def test_process_video_success(tmp_path, monkeypatch):
    import app.main as main
    from app.config import load_settings
    from app.store import Store
    from app.models import Source

    settings = load_settings(env_file=tmp_path / "none.env", data_dir=tmp_path / "data")
    store = Store(settings.db_path)
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="video", title="Video wordt opgehaald…",
        position=0, included=True, text="", youtube_url="https://youtu.be/x",
        processing=True,
    ))
    fake = {"metadata": {"title": "Echte titel", "url": "https://youtu.be/x",
                          "video_id": "x", "thumbnail": "https://t/t.jpg"},
            "transcript": [{"ts": "0:00", "text": "inhoud over leiderschap"}]}
    monkeypatch.setattr(main.video, "fetch_raw", lambda url, _runner=None: fake)
    monkeypatch.setattr(main, "summarize", lambda text, **kw: "syn")
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "inhoud over leiderschap")

    main.process_video(store, settings, s.id, "https://youtu.be/x")

    got = store.list_sources(p.id)[0]
    assert got.processing is False
    assert got.title == "Echte titel"
    assert got.synopsis == "syn"
    assert got.quote == "inhoud over leiderschap"


def test_processing_source_shows_indicator_and_polls(tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "process_video",
                        lambda store, settings, source_id, url: None)  # stays pending
    client = _client(tmp_path, monkeypatch)
    client.post("/sources/video", data={"url": "https://youtu.be/x"})
    body = client.get("/").text
    assert "bezig met ophalen" in body
    assert 'hx-get="/sources"' in body          # list polls while pending


def test_no_polling_when_nothing_processing(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    body = client.get("/").text
    assert 'hx-get="/sources"' not in body


def test_process_video_failure_sets_failed_title(tmp_path, monkeypatch):
    import app.main as main
    from app.config import load_settings
    from app.store import Store
    from app.models import Source

    settings = load_settings(env_file=tmp_path / "none.env", data_dir=tmp_path / "data")
    store = Store(settings.db_path)
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="video", title="Video wordt opgehaald…",
        position=0, included=True, text="", processing=True,
    ))

    def boom(url, _runner=None):
        raise RuntimeError("playwright kapot")

    monkeypatch.setattr(main.video, "fetch_raw", boom)
    main.process_video(store, settings, s.id, "https://youtu.be/x")

    got = store.list_sources(p.id)[0]
    assert got.processing is False and got.title == "Ophalen mislukt"
