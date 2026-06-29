from __future__ import annotations

import html as _html
from pathlib import Path
from urllib.parse import urlparse

from app.models import Source

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Archivo:wght@400;500;600&"
    'family=Spectral:ital,wght@0,400;0,500;0,600;1,500&display=swap">'
)

_CSS = """
  *{box-sizing:border-box}
  body{margin:0;background:#e7e2d6;font-family:'Archivo',system-ui,sans-serif;color:#211d18;-webkit-font-smoothing:antialiased}
  .wrap{display:flex;flex-direction:column;align-items:center;gap:26px;padding:30px 20px 60px}
  .cover{width:880px;max-width:100%;text-align:center;padding:30px 0 0}
  .cover h1{font:600 40px/1.12 'Spectral';margin:0}
  .cover .reader-meta{font:600 12px 'Archivo';letter-spacing:.16em;text-transform:uppercase;color:#8a8175;margin-top:10px}
  .sheet{width:880px;max-width:100%;background:#fbf9f4;box-shadow:0 4px 24px rgba(33,29,24,.12)}
  .band{display:flex;align-items:baseline;gap:14px;padding:18px 64px;background:#211d18;color:#f7f4ef}
  .band-n{font:500 13px 'Spectral';color:#f78ac4}
  .band-t{font:600 16px 'Archivo';letter-spacing:.02em}
  .band-r{margin-left:auto;font:600 11px 'Archivo';letter-spacing:.16em;text-transform:uppercase;color:#9a9388}
  .pad{padding:46px 64px 56px}
  .r-quote{font:500 25px/1.42 'Spectral';font-style:italic;border-left:3px solid #e5007d;padding:2px 0 2px 24px;margin:0 0 30px;text-wrap:pretty}
  .page-img{display:block;width:100%;box-shadow:0 1px 6px rgba(33,29,24,.10);margin:14px 0}
  .video a{display:inline-block}
  .video img{max-width:480px;width:100%;border-radius:8px}
  .synopsis{font:400 16px/1.6 'Spectral';color:#3a352d;margin-top:14px}
  .questions{margin-top:34px;border-top:1px solid #e6e0d3;padding-top:22px}
  .questions h3{font:600 12px 'Archivo';letter-spacing:.16em;text-transform:uppercase;color:#e5007d;margin:0 0 12px}
  .questions ol{margin:0;padding-left:1.2em}
  .questions li{font:400 16px/1.55 'Spectral';margin:8px 0}
  @media print{body{background:#fff}.sheet{box-shadow:none}}
"""

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
{fonts}
<style>{styles}</style>
</head>
<body>
<div class="wrap">
{cover}
{body}
</div>
</body>
</html>
"""


def _safe_url(value: str | None) -> str:
    value = value or ""
    return value if urlparse(value).scheme in ("http", "https") else ""


def _copy_into(src: Path, out_dir: Path) -> Path:
    dest = out_dir / src.name
    if src != dest:
        dest.write_bytes(src.read_bytes())
    return dest


def _band_meta(s: Source) -> str:
    if s.kind == "video":
        return f"Bron · Video · {s.duration}" if s.duration else "Bron · Video"
    if s.page_count:
        return f"Bron · PDF · {s.page_count} p."
    return "Bron · PDF"


def _video_content(s: Source) -> str:
    url = _html.escape(_safe_url(s.youtube_url))
    thumb = _html.escape(_safe_url(s.thumbnail_url))
    title = _html.escape(s.title)
    synopsis = _html.escape(s.synopsis or "")
    synopsis_html = f'\n    <p class="synopsis">{synopsis}</p>' if synopsis else ""
    return (
        '<div class="video">\n'
        f'    <a href="{url}" target="_blank" rel="noopener">'
        f'<img src="{thumb}" alt="{title}"></a>'
        f"{synopsis_html}\n"
        "  </div>"
    )


def _document_content(s: Source, out_dir: Path, render_pdf_pages) -> str:
    pages = render_pdf_pages(s.filename) if s.filename else []
    imgs = []
    for p in pages:
        p = Path(p)
        try:
            rel = p.relative_to(out_dir).as_posix()
        except ValueError:
            rel = _copy_into(p, out_dir).name
        imgs.append(f'    <img class="page-img" src="{_html.escape(rel)}" alt="">')
    return "\n".join(imgs)


def _render_questions(questions: list[str]) -> str:
    items = "\n".join(f"      <li>{_html.escape(q)}</li>" for q in questions)
    return (
        '<section class="questions">\n'
        "      <h3>Verdiepende vragen</h3>\n"
        f"      <ol>\n{items}\n      </ol>\n"
        "    </section>"
    )


def _render_sheet(
    s: Source, number: int, content_html: str, quote: str | None, questions: list[str]
) -> str:
    title = _html.escape(s.title)
    meta = _html.escape(_band_meta(s))
    parts: list[str] = []
    if quote:
        parts.append(f'    <blockquote class="r-quote">{_html.escape(quote)}</blockquote>')
    if content_html:
        parts.append(content_html)
    if questions:
        parts.append(_render_questions(questions))
    pad = "\n".join(parts)
    return (
        '<section class="sheet">\n'
        f'  <div class="band"><span class="band-n">{number:02d}</span>'
        f'<span class="band-t">{title}</span>'
        f'<span class="band-r">{meta}</span></div>\n'
        f'  <div class="pad">\n{pad}\n  </div>\n'
        "</section>"
    )


def render_reader(
    project_name: str,
    sources: list[Source],
    out_dir: Path,
    *,
    render_pdf_pages,
    subtitle: str | None = None,
    questions_by_source: dict[int, list[str]] | None = None,
    quotes_by_source: dict[int, str] | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    qbs = questions_by_source or {}
    quotes = quotes_by_source or {}
    sheets: list[str] = []
    number = 0
    for s in sources:
        if not s.included:
            continue
        number += 1
        if s.kind == "video":
            content = _video_content(s)
        else:
            content = _document_content(s, out_dir, render_pdf_pages)
        sheets.append(
            _render_sheet(s, number, content, quotes.get(s.id), qbs.get(s.id) or [])
        )

    subtitle_html = (
        f'<p class="reader-meta">{_html.escape(subtitle)}</p>' if subtitle else ""
    )
    cover = (
        '<header class="cover">\n'
        f"  <h1>{_html.escape(project_name)}</h1>\n"
        f"  {subtitle_html}\n"
        "</header>"
    )
    page = _PAGE_TEMPLATE.format(
        title=_html.escape(project_name),
        fonts=_FONTS,
        styles=_CSS,
        cover=cover,
        body="\n".join(sheets),
    )
    out = out_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    return out
