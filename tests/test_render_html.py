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
