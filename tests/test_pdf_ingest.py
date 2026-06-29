import pytest
from app.ingest import pdf


@pytest.fixture
def leiderschap_pdf(sample_pdf_dir):
    p = sample_pdf_dir / "Over leiderschap_DIG.pdf"
    if not p.exists():
        pytest.skip("sample PDF ontbreekt")
    return p


def test_page_count_positive(leiderschap_pdf):
    assert pdf.page_count(leiderschap_pdf) > 0


def test_extract_text_returns_nonempty(leiderschap_pdf):
    text = pdf.extract_text(leiderschap_pdf)
    assert isinstance(text, str)
    assert len(text.strip()) > 50


def test_has_text_layer_true_for_digital_pdf(leiderschap_pdf):
    assert pdf.has_text_layer(leiderschap_pdf) is True


def test_render_pages_to_png_creates_one_per_page(leiderschap_pdf, tmp_path):
    paths = pdf.render_pages_to_png(leiderschap_pdf, tmp_path)
    assert len(paths) == pdf.page_count(leiderschap_pdf)
    assert all(p.exists() and p.suffix == ".png" for p in paths)
    assert paths[0].name == "page-0001.png"
