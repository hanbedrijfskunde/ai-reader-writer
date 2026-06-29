from __future__ import annotations

import html as _html
from pathlib import Path
from urllib.parse import urlparse

from app.models import Source

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Archivo:wght@500;600;700;800&"
    "family=Spectral:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400;1,500"
    '&display=swap">'
)

# Design system — "Het Naslagwerk" (HAN reader): Spectral serif voor tekst &
# koppen, Archivo voor labels/meta, HAN-magenta als spaarzaam accent en het
# springplank-motief (gekantelde balk, -20°). Klassenamen worden door de
# rendertests vastgehouden; pas ze niet ongemerkt aan.
_CSS = """
  *{box-sizing:border-box}
  body{margin:0;background:#e7e2d6;font-family:'Archivo',system-ui,sans-serif;color:#211d18;-webkit-font-smoothing:antialiased}
  /* sticky merk-nav */
  .nav{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:14px;height:54px;padding:0 26px;background:rgba(247,244,239,.86);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid #ddd6c8}
  .nav-spr{width:26px;height:8px;background:#e5007d;transform:rotate(-20deg);flex:none}
  .nav-mark{font:800 18px 'Archivo';letter-spacing:.02em;color:#211d18}
  .nav-title{font:600 13px 'Archivo';letter-spacing:.01em;color:#6b645a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .nav-sp{flex:1}
  .nav-meta{font:600 11px 'Archivo';letter-spacing:.14em;text-transform:uppercase;color:#9a9388;white-space:nowrap}
  .wrap{display:flex;flex-direction:column;align-items:center;gap:26px;padding:30px 20px 64px}
  /* omslag */
  .cover{position:relative;width:880px;max-width:100%;background:#f7f4ef;box-shadow:0 4px 24px rgba(33,29,24,.12);overflow:hidden;display:flex;flex-direction:column;min-height:520px;scroll-margin-top:66px}
  .cov-spr{position:absolute;background:#e5007d}
  .s1{width:230px;height:40px;top:118px;right:34px;transform:rotate(-20deg)}
  .s2{width:118px;height:22px;top:184px;right:148px;transform:rotate(-20deg);background:#f7b0d4}
  .s3{width:78px;height:15px;top:94px;right:208px;transform:rotate(-20deg);background:#211d18}
  .cov-top{padding:42px 56px 0;position:relative;z-index:2;display:flex;align-items:center;gap:12px}
  .cov-mark{font:800 22px 'Archivo';letter-spacing:.02em;color:#211d18}
  .cov-mid{margin-top:auto;padding:0 56px;position:relative;z-index:2}
  .cov-kick{font:700 12px 'Archivo';letter-spacing:.26em;text-transform:uppercase;color:#e5007d;margin:0 0 18px}
  .cover h1{font:600 clamp(40px,7vw,76px)/1.0 'Spectral';letter-spacing:-.02em;margin:0;max-width:660px;text-wrap:balance}
  .cov-foot{margin-top:34px;padding:24px 56px 48px;position:relative;z-index:2;border-top:2px solid #211d18;margin-left:56px;margin-right:56px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:18px;padding-left:0;padding-right:0}
  .reader-meta{font:600 12px 'Archivo';letter-spacing:.16em;text-transform:uppercase;color:#8a8175;margin:0}
  .cov-size{font:600 12px 'Archivo';letter-spacing:.16em;text-transform:uppercase;color:#8a8175;margin:0}
  /* vel + hoofdstukband */
  .sheet{width:880px;max-width:100%;background:#fbf9f4;box-shadow:0 4px 24px rgba(33,29,24,.12);scroll-margin-top:66px}
  .band{display:flex;align-items:baseline;gap:14px;padding:18px 64px;background:#211d18;color:#f7f4ef}
  .band-n{font:500 13px 'Spectral';color:#f78ac4}
  .band-t{font:600 16px 'Archivo';letter-spacing:.02em}
  .band-r{margin-left:auto;font:600 11px 'Archivo';letter-spacing:.16em;text-transform:uppercase;color:#9a9388}
  .pad{padding:50px 64px 58px}
  .r-quote{font:500 25px/1.42 'Spectral';font-style:italic;color:#211d18;border-left:3px solid #e5007d;padding:2px 0 2px 24px;margin:0 0 30px;text-wrap:pretty}
  .r-quote cite{display:block;font:600 12px 'Archivo';font-style:normal;color:#8a8175;letter-spacing:.04em;margin-top:12px}
  /* bronpagina's */
  .page-img{display:block;width:100%;margin:16px 0;border:1px solid #e1dacb;background:#fff;box-shadow:0 1px 8px rgba(33,29,24,.08)}
  /* video */
  .video a{display:inline-block;position:relative}
  .video img{max-width:520px;width:100%;border-radius:8px;border:1px solid #e1dacb;box-shadow:0 1px 8px rgba(33,29,24,.08)}
  .synopsis{font:400 16.5px/1.7 'Spectral';color:#2b261f;margin:18px 0 0;max-width:62ch;text-wrap:pretty}
  /* verdiepende vragen */
  .questions{margin-top:38px;border-top:1px solid #e6e0d3;padding-top:26px}
  .questions h3{display:inline-block;font:700 10px 'Archivo';letter-spacing:.18em;text-transform:uppercase;color:#e5007d;border:1px solid #f4bcdb;border-radius:3px;padding:4px 9px;margin:0 0 18px}
  .questions ol{margin:0;padding:0;list-style:none;counter-reset:q}
  .questions li{counter-increment:q;position:relative;padding-left:42px;font:400 16.5px/1.62 'Spectral';color:#2b261f;margin:14px 0;text-wrap:pretty}
  .questions li::before{content:counter(q,decimal-leading-zero);position:absolute;left:0;top:2px;font:600 13px 'Archivo';color:#e5007d}
  @media (max-width:720px){
    .nav{padding:0 18px;gap:10px}.nav-title{display:none}
    .cov-top{padding:30px 26px 0}.cov-mid{padding:0 26px}
    .cov-foot{margin-left:26px;margin-right:26px;padding-bottom:38px}
    .cover h1{max-width:none}
    .band{padding:14px 26px}.pad{padding:34px 26px 40px}
  }
  @media print{
    @page{margin:14mm}
    body{background:#fff}.nav{display:none}
    /* block-flow i.p.v. flex: page-breaks zijn alleen betrouwbaar in block
       containers (flex/grid negeren break-before in veel browsers) */
    .wrap{display:block;gap:0;padding:0}
    .sheet,.cover{box-shadow:none;border:none;width:auto;margin:0 auto;max-width:880px}
    /* elke bron-sectie op een nieuwe pagina; omslag blijft pagina 1 */
    .sheet{page-break-before:always;break-before:page}
    .cover{page-break-after:always;break-after:page}
    .questions,.r-quote,.page-img,.video{break-inside:avoid}
  }
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
<nav class="nav">
  <span class="nav-spr"></span><span class="nav-mark">HAN</span>
  <span class="nav-title">{nav_title}</span>
  <span class="nav-sp"></span>
  {nav_meta}
</nav>
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


def _size_label(n_docs: int, n_videos: int) -> str:
    parts: list[str] = []
    if n_docs:
        parts.append(f"{n_docs} bron" if n_docs == 1 else f"{n_docs} bronnen")
    if n_videos:
        parts.append(f"{n_videos} video" if n_videos == 1 else f"{n_videos} video's")
    return " · ".join(parts)


def _render_cover(
    project_name: str, subtitle: str | None, n_docs: int, n_videos: int
) -> str:
    foot_items: list[str] = []
    if subtitle:
        foot_items.append(f'<p class="reader-meta">{_html.escape(subtitle)}</p>')
    size = _size_label(n_docs, n_videos)
    if size:
        foot_items.append(f'<p class="cov-size">{_html.escape(size)}</p>')
    foot = (
        f'\n  <div class="cov-foot">{"".join(foot_items)}</div>' if foot_items else ""
    )
    return (
        '<header class="cover" id="omslag">\n'
        '  <span class="cov-spr s3"></span><span class="cov-spr s2"></span>'
        '<span class="cov-spr s1"></span>\n'
        '  <div class="cov-top"><span class="nav-spr"></span>'
        '<span class="cov-mark">HAN</span></div>\n'
        '  <div class="cov-mid">\n'
        '    <p class="cov-kick">Reader</p>\n'
        f"    <h1>{_html.escape(project_name)}</h1>\n"
        "  </div>"
        f"{foot}\n"
        "</header>"
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

    included = [s for s in sources if s.included]
    n_docs = sum(1 for s in included if s.kind != "video")
    n_videos = sum(1 for s in included if s.kind == "video")
    cover = _render_cover(project_name, subtitle, n_docs, n_videos)

    nav_meta = (
        f'<span class="nav-meta">{_html.escape(subtitle)}</span>' if subtitle else ""
    )
    page = _PAGE_TEMPLATE.format(
        title=_html.escape(project_name),
        fonts=_FONTS,
        styles=_CSS,
        nav_title=_html.escape(project_name),
        nav_meta=nav_meta,
        cover=cover,
        body="\n".join(sheets),
    )
    out = out_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    return out
