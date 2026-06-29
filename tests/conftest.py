import pytest


@pytest.fixture
def sample_pdf_dir():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "source-docs"
