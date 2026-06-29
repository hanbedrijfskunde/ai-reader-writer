from pathlib import Path

from app.models import Source
from app.render import html


def _video(title: str) -> Source:
    return Source(
        id=1, project_id=1, kind="video", title=title, position=0,
        included=True, text="t", youtube_url="https://youtu.be/abc",
        video_id="abc", channel="Ch", duration="1:00",
        thumbnail_url="https://img/thumb.jpg", synopsis="Synopsis hier.",
    )


def _doc(title: str) -> Source:
    return Source(
        id=2, project_id=1, kind="document", title=title, position=1,
        included=True, text="t", filename="doc.pdf", page_count=2,
    )


def test_render_writes_index_html(tmp_path):
    out = html.render_reader(
        "Module A", [_video("Vid")], tmp_path, render_pdf_pages=lambda fn: [],
    )
    assert out == tmp_path / "index.html"
    content = out.read_text(encoding="utf-8")
    assert "Module A" in content
    assert "Vid" in content
    assert "Synopsis hier." in content
    assert "https://youtu.be/abc" in content
    assert "https://img/thumb.jpg" in content


def test_render_includes_pdf_page_images(tmp_path):
    page = tmp_path / "page-0001.png"
    page.write_bytes(b"\x89PNG\r\n")
    out = html.render_reader(
        "M", [_doc("Doc")], tmp_path, render_pdf_pages=lambda fn: [page],
    )
    content = out.read_text(encoding="utf-8")
    assert "page-0001.png" in content
    assert "<img" in content


def test_render_skips_excluded_sources(tmp_path):
    excl = _video("Verborgen")
    excl.included = False
    out = html.render_reader("M", [excl], tmp_path, render_pdf_pages=lambda fn: [])
    assert "Verborgen" not in out.read_text(encoding="utf-8")


def test_render_preserves_source_order(tmp_path):
    out = html.render_reader(
        "Order Test", [_video("AAA"), _doc("BBB")], tmp_path, render_pdf_pages=lambda fn: [],
    )
    content = out.read_text(encoding="utf-8")
    assert content.index("AAA") < content.index("BBB")


def test_render_escapes_html_in_title(tmp_path):
    v = _video("x")
    v.title = "<script>alert(1)</script>"
    out = html.render_reader("Escape Test", [v], tmp_path, render_pdf_pages=lambda fn: [])
    content = out.read_text(encoding="utf-8")
    assert "<script>" not in content
    assert "&lt;script&gt;" in content


def test_render_multiple_documents_do_not_collide(tmp_path):
    d1 = _doc("First"); d1.filename = "alpha.pdf"
    d2 = _doc("Second"); d2.filename = "beta.pdf"
    def stub(fn):
        sub = tmp_path / Path(fn).stem
        sub.mkdir(parents=True, exist_ok=True)
        p = sub / "page-0001.png"; p.write_bytes(b"\x89PNG\r\n")
        return [p]
    out = html.render_reader("M", [d1, d2], tmp_path, render_pdf_pages=stub)
    content = out.read_text(encoding="utf-8")
    assert "alpha/page-0001.png" in content
    assert "beta/page-0001.png" in content


def test_render_strips_javascript_url_scheme(tmp_path):
    v = _video("x")
    v.youtube_url = "javascript:alert(1)"
    out = html.render_reader("M", [v], tmp_path, render_pdf_pages=lambda fn: [])
    content = out.read_text(encoding="utf-8")
    assert "javascript:alert(1)" not in content
    assert 'href=""' in content  # scheme allowlisted to empty


def test_render_includes_subtitle(tmp_path):
    out = html.render_reader("Mijn Titel", [], tmp_path,
                             render_pdf_pages=lambda fn: [],
                             subtitle="BK-101 · 2025-2026")
    content = out.read_text(encoding="utf-8")
    assert "<h1>Mijn Titel</h1>" in content
    assert "BK-101 · 2025-2026" in content
    assert 'class="reader-meta"' in content


def test_render_escapes_subtitle(tmp_path):
    out = html.render_reader("T", [], tmp_path, render_pdf_pages=lambda fn: [],
                             subtitle="<script>x</script>")
    content = out.read_text(encoding="utf-8")
    assert "<script>x</script>" not in content
    assert "&lt;script&gt;" in content


def test_render_without_subtitle_has_no_meta(tmp_path):
    out = html.render_reader("T", [], tmp_path, render_pdf_pages=lambda fn: [])
    content = out.read_text(encoding="utf-8")
    assert 'class="reader-meta"' not in content


def test_render_video_omits_empty_synopsis_paragraph(tmp_path):
    v = _video("Zonder synopsis")
    v.synopsis = None
    out = html.render_reader("M", [v], tmp_path, render_pdf_pages=lambda fn: [])
    content = out.read_text(encoding="utf-8")
    assert 'class="synopsis"' not in content  # no empty synopsis block
