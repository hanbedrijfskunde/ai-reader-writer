import json
from pathlib import Path

from app.ingest import video

FIX = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_transcript_text_joins_segments():
    raw = _load("sample_video.json")
    text = video.transcript_text(raw)
    assert "Welkom bij deze les" in text
    assert "drie kernstijlen" in text


def test_transcript_text_empty_when_no_segments():
    raw = _load("sample_video_no_transcript.json")
    assert video.transcript_text(raw) == ""


def test_build_source_with_transcript():
    raw = _load("sample_video.json")
    src = video.build_source(
        "https://youtu.be/abc123XYZ_0",
        model="claude-sonnet-4-6",
        claude_key=None,
        _runner=lambda url: raw,
        _summarizer=lambda text, **kw: "Korte synopsis.",
    )
    assert src.kind == "video"
    assert src.title == "Wat is leiderschap?"
    assert src.channel == "HAN Bedrijfskunde"
    assert src.duration == "12:34"
    assert src.thumbnail_url.endswith("maxresdefault.jpg")
    assert src.video_id == "abc123XYZ_0"
    assert "drie kernstijlen" in src.text
    assert src.synopsis == "Korte synopsis."


def test_build_source_without_transcript_has_no_synopsis():
    raw = _load("sample_video_no_transcript.json")
    src = video.build_source(
        "https://youtu.be/noCaps00000",
        model="claude-sonnet-4-6",
        claude_key=None,
        _runner=lambda url: raw,
        _summarizer=lambda text, **kw: "zou niet aangeroepen moeten worden",
    )
    assert src.kind == "video"
    assert src.text == ""
    assert src.synopsis is None
    assert src.thumbnail_url.endswith("maxresdefault.jpg")
