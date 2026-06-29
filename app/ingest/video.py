from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.ai.client import summarize
from app.models import Source

_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "integrations" / "youtube_transcript" / "fetch_transcript.py"
)


def _default_runner(url: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), url, "--json"],
        capture_output=True, text=True, timeout=180,
    )
    # exitcode 2 = ongeldige URL; exitcode 1 = alleen metadata (stdout bevat dan
    # nog geldige JSON), dus alleen op 2 of lege stdout falen.
    if proc.returncode == 2 or not proc.stdout.strip():
        raise ValueError(f"kon video niet ophalen: {proc.stderr.strip() or url}")
    return json.loads(proc.stdout)


def fetch_raw(url: str, _runner=None) -> dict:
    runner = _runner or _default_runner
    return runner(url)


def transcript_text(raw: dict) -> str:
    segments = raw.get("transcript") or []
    return " ".join(s.get("text", "") for s in segments).strip()


def build_source(
    url: str,
    *,
    model: str,
    claude_key: str | None,
    _runner=None,
    _summarizer=None,
) -> Source:
    raw = fetch_raw(url, _runner=_runner)
    meta = raw.get("metadata") or {}
    text = transcript_text(raw)

    synopsis = None
    if text:
        summ = _summarizer or summarize
        synopsis = summ(text, model=model, claude_key=claude_key)

    return Source(
        id=0, project_id=0, kind="video",
        title=meta.get("title") or url, position=0, included=True,
        text=text, youtube_url=meta.get("url") or url,
        video_id=meta.get("video_id"), channel=meta.get("channel"),
        duration=meta.get("duration"), thumbnail_url=meta.get("thumbnail"),
        synopsis=synopsis,
    )
