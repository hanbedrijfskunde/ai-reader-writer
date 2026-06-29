from __future__ import annotations

import html as _html
from pathlib import Path
from urllib.parse import urlparse

from app.models import Source


def _safe_url(value: str | None) -> str:
    """Return the URL only if it uses an http(s) scheme; else empty string.

    Escaping alone does not stop a javascript:/data: scheme in href/src, so we
    allowlist the scheme before the value reaches the exported HTML.
    """
    value = value or ""
    return value if urlparse(value).scheme in ("http", "https") else ""

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
  .source {{ margin-bottom: 3rem; }}
  .page-img {{ display: block; width: 100%; box-shadow: 0 0 4px #ccc; margin: 1rem 0; }}
  .video img {{ max-width: 480px; width: 100%; border-radius: 8px; }}
  .synopsis {{ color: #333; }}
</style>
</head>
<body>
<h1>{title}</h1>
{body}
</body>
</html>
"""


def _copy_into(src: Path, out_dir: Path) -> Path:
    dest = out_dir / src.name
    if src != dest:
        dest.write_bytes(src.read_bytes())
    return dest


def _render_video(s: Source) -> str:
    title = _html.escape(s.title)
    url = _html.escape(_safe_url(s.youtube_url))
    thumb = _html.escape(_safe_url(s.thumbnail_url))
    synopsis = _html.escape(s.synopsis or "")
    return (
        '<section class="source video">\n'
        f"  <h2>{title}</h2>\n"
        f'  <a href="{url}" target="_blank" rel="noopener">'
        f'<img src="{thumb}" alt="{title}"></a>\n'
        f'  <p class="synopsis">{synopsis}</p>\n'
        "</section>"
    )


def _render_document(s: Source, out_dir: Path, render_pdf_pages) -> str:
    title = _html.escape(s.title)
    pages = render_pdf_pages(s.filename) if s.filename else []
    imgs = []
    for p in pages:
        p = Path(p)
        try:
            rel = p.relative_to(out_dir).as_posix()
        except ValueError:
            rel = _copy_into(p, out_dir).name
        imgs.append(f'  <img class="page-img" src="{_html.escape(rel)}" alt="">')
    return (
        '<section class="source document">\n'
        f"  <h2>{title}</h2>\n" + "\n".join(imgs) + "\n</section>"
    )


def render_reader(project_name: str, sources: list[Source], out_dir: Path, *, render_pdf_pages) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    blocks: list[str] = []
    for s in sources:
        if not s.included:
            continue
        if s.kind == "video":
            blocks.append(_render_video(s))
        else:
            blocks.append(_render_document(s, out_dir, render_pdf_pages))

    page = _PAGE_TEMPLATE.format(title=_html.escape(project_name), body="\n".join(blocks))
    out = out_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    return out
