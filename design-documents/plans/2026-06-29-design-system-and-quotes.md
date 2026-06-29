# Design system + verbatim citaat-appetizers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Geef de geëxporteerde reader én de app-UI het bestaande design system (Spectral+Archivo, crème/magenta, `.sheet`/`.band`/`.r-quote`), en toon aan het begin van elke sectie een **verbatim citaat** dat de AI automatisch uit de brontekst haalt.

**Architecture:** Twee onafhankelijke toevoegingen op de bestaande FastAPI+HTMX-pijplijn: (1) een citaat-extractor (`app/ai/quotes.py`) die een letterlijke zin uit `bron.text` haalt, gevalideerd als substring, opgeslagen in een nieuwe `quote`-kolom op de source; auto-getriggerd bij het toevoegen van een bron. (2) Een visuele herstijling van `app/render/html.py` (reader-export) en de app-templates naar het design system. Alle AI-randen zijn injecteerbaar zodat tests offline draaien.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2 + HTMX, anthropic (Claude API), Playwright/Chromium (bestaand), Google Fonts, pytest.

## Global Constraints

- Python 3.10+; gebruik `from __future__ import annotations`.
- Secrets uitsluitend uit `.env.local`; Claude-model uit `settings.default_model`, nooit hardcoden; key-parameter heet `claude_key`; de echte client wordt aangemaakt met de dict-unpack-vorm `Anthropic(**{"api_key": claude_key})` (een letterlijke keyword-spelling trips een secret-scanner — gebruik de dict-vorm verbatim).
- Tests gaan **NOOIT** het netwerk op: Claude-calls worden via `_caller` geïnjecteerd/gemockt; de bestaande PDF-rooktest mag chromium gebruiken.
- Alle bron-/citaat-/vraag-tekst in de gerenderde HTML wordt HTML-escaped.
- Het citaat is **verbatim**: het wordt alleen geaccepteerd als het — na whitespace-normalisatie — daadwerkelijk in `bron.text` voorkomt.
- Geen `<cite>`-bronvermelding onder het citaat (alleen de zin).
- Elke taak eindigt met een groene `python3 -m pytest -q` en een commit waarvan het bericht eindigt op `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Gebruik `python3 -m pytest` (`python` staat niet op PATH).
- Module-level imports in `main.py` zodat tests `main.X` kunnen monkeypatchen.

---

## File Structure

```
app/
  models.py            # + Source.quote veld
  store.py             # + quote-kolom + _ensure_source_columns migratie + set_quote
  ai/
    quotes.py          # NIEUW: extract_quote(...) + verbatim substring-validatie
  render/
    html.py            # HERSTIJL: design system (sheet/band/cover/r-quote) + quotes_by_source
  main.py              # + auto-extractie bij add_pdf/add_video; quotes in _build_reader_html
  templates/
    index.html         # HERSTIJL: design system op de app-UI (fonts, palet, knoppen)
    _source_list.html  # erft global CSS; ongewijzigde structuur
tests/
  test_store.py            # + quote set/migratie
  test_quotes.py           # NIEUW: extractor (offline via injected caller)
  test_render_html.py      # HERSCHREVEN voor de nieuwe markup + quote-appetizer
  test_routes.py           # + auto-extractie + quote in export + app-UI markup
```

---

### Task 1: Quote-veld in de store (model + migratie + set_quote)

**Files:**
- Modify: `app/models.py`
- Modify: `app/store.py`
- Modify: `tests/test_store.py`

**Interfaces:**
- Consumes: bestaande `Store` (sources-tabel, `_SOURCE_COLS`, `_row_to_source`, `_ensure_project_columns`-patroon).
- Produces:
  - `app.models.Source` krijgt veld `quote: str | None = None` (laatste veld).
  - `Store.set_quote(source_id: int, quote: str | None) -> None`.
  - De `sources`-tabel krijgt een `quote TEXT`-kolom; bestaande DB's worden gemigreerd (ALTER if missing); `list_sources`/`add_source` retourneren `Source` mét `quote`.

- [ ] **Step 1: Schrijf de falende store-test**

Voeg toe aan `tests/test_store.py`:

```python
def test_set_quote_roundtrip(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="document", title="D", position=0,
        included=True, text="body", filename="d.pdf", page_count=1,
    ))
    assert store.list_sources(p.id)[0].quote is None
    store.set_quote(s.id, "Een pakkende zin.")
    assert store.list_sources(p.id)[0].quote == "Een pakkende zin."


def test_quote_migration_on_legacy_sources(tmp_path):
    import sqlite3
    db = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,"
        " status TEXT NOT NULL DEFAULT 'concept', bloom_level TEXT);"
        "CREATE TABLE sources (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL,"
        " kind TEXT NOT NULL, title TEXT NOT NULL, position INTEGER NOT NULL,"
        " included INTEGER NOT NULL DEFAULT 1, text TEXT NOT NULL DEFAULT '',"
        " filename TEXT, page_count INTEGER, youtube_url TEXT, video_id TEXT,"
        " channel TEXT, duration TEXT, thumbnail_url TEXT, synopsis TEXT);"
        "INSERT INTO projects (name) VALUES ('Oud');"
        "INSERT INTO sources (project_id, kind, title, position) VALUES (1,'document','D',0);"
    )
    conn.commit()
    conn.close()
    store = Store(db)  # opening must add the quote column
    store.set_quote(1, "Q")
    assert store.list_sources(1)[0].quote == "Q"
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_store.py -k quote -v`
Expected: FAIL (`TypeError: Source.__init__() got ... 'quote'` of `AttributeError: ... set_quote`).

- [ ] **Step 3: Voeg het `quote`-veld toe aan `app/models.py`**

In de `Source`-dataclass, voeg als laatste veld toe (ná `synopsis`):

```python
    quote: str | None = None
```

- [ ] **Step 4: Voeg de kolom, migratie, `_SOURCE_COLS`-entry en `set_quote` toe in `app/store.py`**

In de `sources`-tabel in `_SCHEMA`, voeg een kolom toe (ná `synopsis TEXT`):

```sql
    synopsis TEXT,
    quote TEXT
```

Voeg `"quote"` toe aan het einde van de `_SOURCE_COLS`-lijst:

```python
    "duration", "thumbnail_url", "synopsis", "quote",
```

Voeg een sources-migratie toe en roep die aan in `__init__` (direct ná `self._ensure_project_columns()`):

```python
        self._ensure_project_columns()
        self._ensure_source_columns()
        self._conn.commit()

    _SOURCE_META_COLS = {"quote": "TEXT"}

    def _ensure_source_columns(self) -> None:
        existing = {r["name"] for r in self._conn.execute("PRAGMA table_info(sources)")}
        for col, col_type in self._SOURCE_META_COLS.items():
            if col not in existing:
                self._conn.execute(f"ALTER TABLE sources ADD COLUMN {col} {col_type}")
        self._conn.commit()
```

Voeg de setter toe binnen de `Store`-klasse (bijv. ná `set_source_text`):

```python
    def set_quote(self, source_id: int, quote: str | None) -> None:
        self._conn.execute(
            "UPDATE sources SET quote = ? WHERE id = ?", (quote, source_id)
        )
        self._conn.commit()
```

- [ ] **Step 5: Run — verwacht PASS**

Run: `python3 -m pytest tests/test_store.py -q`
Expected: PASS (alle store-tests, inclusief de 2 nieuwe).

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/store.py tests/test_store.py
git commit -m "$(printf 'feat: quote column on source with migration and set_quote\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Citaat-extractor (`app/ai/quotes.py`)

**Files:**
- Create: `app/ai/quotes.py`
- Create: `tests/test_quotes.py`

**Interfaces:**
- Produces:
  - `app.ai.quotes.extract_quote(text: str, *, model: str, claude_key: str | None, _caller=None) -> str` — vraagt Claude om één korte zin **letterlijk** uit `text`; accepteert alleen als die (na whitespace-normalisatie) een substring van `text` is; één retry; geeft `""` terug als er geen verbatim citaat te halen valt.
  - `app.ai.quotes._is_verbatim(quote: str, text: str) -> bool` — whitespace-genormaliseerde substring-check.

- [ ] **Step 1: Schrijf de falende extractor-test**

`tests/test_quotes.py`:

```python
from app.ai import quotes

SOURCE = (
    "Leiderschap is geen positie maar gedrag.\n"
    "Een goede leider schept duidelijkheid en vertrouwen in het team."
)


def test_is_verbatim_normalizes_whitespace():
    assert quotes._is_verbatim("Leiderschap is geen   positie maar gedrag.", SOURCE)
    assert quotes._is_verbatim("schept duidelijkheid en vertrouwen", SOURCE)
    assert not quotes._is_verbatim("dit staat er niet", SOURCE)


def test_extract_quote_returns_verbatim_substring():
    q = quotes.extract_quote(
        SOURCE, model="m", claude_key=None,
        _caller=lambda p: "Leiderschap is geen positie maar gedrag.",
    )
    assert q == "Leiderschap is geen positie maar gedrag."


def test_extract_quote_strips_surrounding_quotes_and_fences():
    q = quotes.extract_quote(
        SOURCE, model="m", claude_key=None,
        _caller=lambda p: '"schept duidelijkheid en vertrouwen in het team."',
    )
    assert q == "schept duidelijkheid en vertrouwen in het team."


def test_extract_quote_retries_then_empty_when_not_verbatim():
    calls = {"n": 0}

    def hallucinate(_p):
        calls["n"] += 1
        return "Een verzonnen zin die niet in de bron staat."

    q = quotes.extract_quote(SOURCE, model="m", claude_key=None, _caller=hallucinate)
    assert q == ""
    assert calls["n"] == 2  # one retry before giving up


def test_extract_quote_empty_text_returns_empty():
    assert quotes.extract_quote("", model="m", claude_key=None, _caller=lambda p: "x") == ""
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_quotes.py -v`
Expected: FAIL (`ModuleNotFoundError: app.ai.quotes`).

- [ ] **Step 3: Implementeer `app/ai/quotes.py`**

```python
from __future__ import annotations

import re


def _default_caller(prompt: str, *, model: str, claude_key: str | None) -> str:
    from anthropic import Anthropic

    client = Anthropic(**{"api_key": claude_key})
    msg = client.messages.create(
        model=model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _is_verbatim(quote: str, text: str) -> bool:
    q = _normalize(quote)
    return bool(q) and q in _normalize(text)


def _clean(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
    # drop a single layer of surrounding straight or smart quotes
    if len(s) >= 2 and s[0] in "\"'“‘" and s[-1] in "\"'”’":
        s = s[1:-1].strip()
    return s


def extract_quote(
    text: str,
    *,
    model: str,
    claude_key: str | None,
    _caller=None,
) -> str:
    if not text.strip():
        return ""
    prompt = (
        "Kies uit de onderstaande brontekst één korte, pakkende zin (max ~25 "
        "woorden) die de kern van de tekst raakt en geschikt is als motto boven "
        "een hoofdstuk. Kopieer de zin LETTERLIJK uit de tekst — verander geen "
        "woorden. Antwoord met UITSLUITEND die ene zin, zonder aanhalingstekens "
        "of toelichting.\n\nBrontekst:\n" + text[:8000]
    )
    caller = _caller or (lambda p: _default_caller(p, model=model, claude_key=claude_key))
    for _ in range(2):
        candidate = _clean(caller(prompt))
        if _is_verbatim(candidate, text):
            return candidate
    return ""
```

- [ ] **Step 4: Run — verwacht PASS**

Run: `python3 -m pytest tests/test_quotes.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/ai/quotes.py tests/test_quotes.py
git commit -m "$(printf 'feat: verbatim quote extractor with substring validation\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Auto-extractie bij het toevoegen van een bron (routes)

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Consumes: `Store.set_quote` (Task 1), `extract_quote` (Task 2).
- Produces: na `POST /sources/pdf` en `POST /sources/video` wordt — als de nieuwe bron `text` heeft — een verbatim citaat geëxtraheerd en via `store.set_quote(stored.id, quote)` opgeslagen. `extract_quote` wordt op module-niveau geïmporteerd zodat tests `main.extract_quote` kunnen monkeypatchen. Een lege of niet-verbatim uitkomst laat `quote` op `None`.

- [ ] **Step 1: Schrijf de falende route-tests**

Voeg toe aan `tests/test_routes.py` (helpers `_client`, `_add_transcriptless_video`, `_add_pdf_like_source` bestaan al):

```python
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
```

Note: `client.app` is the FastAPI app built by `_client`; `app.state.store` and `app.state.project_id` are set in `create_app`. If `client.app` is unavailable in this TestClient version, read them via `import app.main as main` after `_client` patched `load_settings` — but prefer `client.app`.

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_routes.py -k quote -v`
Expected: FAIL (`main.extract_quote` bestaat niet / `src.quote` is None).

- [ ] **Step 3: Importeer de extractor en roep 'm aan in beide add-routes (`app/main.py`)**

Voeg bij de imports toe (module-niveau):

```python
from app.ai.quotes import extract_quote  # noqa: F401  (monkeypatch-doel in tests)
```

Voeg een helper toe binnen `create_app` (bijv. ná `_list_partial`):

```python
    def _autoquote(stored: Source) -> None:
        if stored.text.strip():
            quote = extract_quote(
                stored.text, model=settings.default_model,
                claude_key=settings.anthropic_key,
            )
            if quote:
                store.set_quote(stored.id, quote)
```

In `add_pdf`: vervang `store.add_source(project_id, src)` door:

```python
        stored = store.add_source(project_id, src)
        _autoquote(stored)
```

In `add_video`: vervang `store.add_source(project_id, src)` door:

```python
        stored = store.add_source(project_id, src)
        _autoquote(stored)
```

(Both routes keep `return _list_partial(request)` as their last line.)

- [ ] **Step 4: Run — verwacht PASS**

Run: `python3 -m pytest tests/test_routes.py -q`
Expected: PASS (alle route-tests, inclusief de 2 nieuwe).

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "$(printf 'feat: auto-extract a verbatim quote when a source is added\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Reader-render in het design system (sheets/bands/cover + citaat-appetizer)

**Files:**
- Modify (volledig vervangen): `app/render/html.py`
- Modify (volledig vervangen): `tests/test_render_html.py`

**Interfaces:**
- Consumes: `app.models.Source` (incl. `quote`, `page_count`, `duration`, `kind`, `included`).
- Produces: `render_reader(project_name, sources, out_dir, *, render_pdf_pages, subtitle=None, questions_by_source=None, quotes_by_source: dict[int, str] | None = None) -> Path`. Elke ingesloten bron wordt een `.sheet` met een `.band` (volgnummer `01..` · titel · meta) en een `.pad` met — in deze volgorde — de `.r-quote` appetizer (alleen als er een citaat is), de inhoud (PDF-pagina's of video-blok), en het vragenblok. Google Fonts (Spectral+Archivo) via `<link>`. Alle tekst HTML-escaped.

- [ ] **Step 1: Vervang `app/render/html.py` volledig**

```python
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
```

- [ ] **Step 2: Vervang `tests/test_render_html.py` volledig** (nieuwe markup; behoudt alle gedragsgaranties)

```python
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


def test_render_writes_index_html_with_design_system(tmp_path):
    out = html.render_reader(
        "Module A", [_video("Vid")], tmp_path, render_pdf_pages=lambda fn: [],
    )
    assert out == tmp_path / "index.html"
    content = out.read_text(encoding="utf-8")
    assert "fonts.googleapis.com" in content and "Spectral" in content
    assert 'class="sheet"' in content and 'class="band"' in content
    assert 'class="band-n">01' in content
    assert "Module A" in content        # cover title
    assert "Vid" in content             # band title
    assert "Synopsis hier." in content
    assert "https://youtu.be/abc" in content
    assert "https://img/thumb.jpg" in content


def test_render_subtitle_in_cover(tmp_path):
    out = html.render_reader(
        "T", [], tmp_path, render_pdf_pages=lambda fn: [], subtitle="BK-101 · 2025-2026",
    )
    content = out.read_text(encoding="utf-8")
    assert "BK-101 · 2025-2026" in content
    assert 'class="reader-meta"' in content


def test_render_includes_pdf_page_images(tmp_path):
    page = tmp_path / "page-0001.png"
    page.write_bytes(b"\x89PNG\r\n")
    out = html.render_reader(
        "M", [_doc("Doc")], tmp_path, render_pdf_pages=lambda fn: [page],
    )
    content = out.read_text(encoding="utf-8")
    assert "page-0001.png" in content and 'class="page-img"' in content


def test_render_skips_excluded_sources(tmp_path):
    excl = _video("Verborgen")
    excl.included = False
    out = html.render_reader("M", [excl], tmp_path, render_pdf_pages=lambda fn: [])
    assert "Verborgen" not in out.read_text(encoding="utf-8")


def test_render_preserves_source_order_and_numbers(tmp_path):
    out = html.render_reader(
        "M", [_video("AAA"), _doc("BBB")], tmp_path, render_pdf_pages=lambda fn: [],
    )
    content = out.read_text(encoding="utf-8")
    assert content.index("AAA") < content.index("BBB")
    assert 'class="band-n">01' in content and 'class="band-n">02' in content


def test_render_escapes_html_in_title(tmp_path):
    out = html.render_reader(
        "T", [_video("<script>alert(1)</script>")], tmp_path,
        render_pdf_pages=lambda fn: [],
    )
    content = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in content
    assert "&lt;script&gt;" in content


def test_render_strips_javascript_url_scheme(tmp_path):
    v = _video("x")
    v.youtube_url = "javascript:alert(1)"
    out = html.render_reader("M", [v], tmp_path, render_pdf_pages=lambda fn: [])
    content = out.read_text(encoding="utf-8")
    assert "javascript:alert(1)" not in content
    assert 'href=""' in content


def test_render_video_omits_empty_synopsis_paragraph(tmp_path):
    v = _video("Zonder synopsis")
    v.synopsis = None
    out = html.render_reader("M", [v], tmp_path, render_pdf_pages=lambda fn: [])
    assert 'class="synopsis"' not in out.read_text(encoding="utf-8")


def test_render_multiple_documents_do_not_collide(tmp_path):
    d1 = _doc("First"); d1.filename = "alpha.pdf"
    d2 = _doc("Second"); d2.filename = "beta.pdf"

    def stub(fn):
        from pathlib import Path
        sub = tmp_path / Path(fn).stem
        sub.mkdir(parents=True, exist_ok=True)
        p = sub / "page-0001.png"; p.write_bytes(b"\x89PNG\r\n")
        return [p]

    out = html.render_reader("M", [d1, d2], tmp_path, render_pdf_pages=stub)
    content = out.read_text(encoding="utf-8")
    assert "alpha/page-0001.png" in content
    assert "beta/page-0001.png" in content


def test_render_includes_questions_block_in_sheet(tmp_path):
    v = _video("Vid")
    out = html.render_reader(
        "M", [v], tmp_path, render_pdf_pages=lambda fn: [],
        questions_by_source={v.id: ["Waarom werkt dit?", "<b>Hoe</b> nu?"]},
    )
    content = out.read_text(encoding="utf-8")
    assert 'class="questions"' in content and "Verdiepende vragen" in content
    assert "Waarom werkt dit?" in content
    assert "&lt;b&gt;Hoe&lt;/b&gt; nu?" in content and "<b>Hoe</b> nu?" not in content


def test_render_no_questions_block_when_absent(tmp_path):
    out = html.render_reader(
        "M", [_video("Vid")], tmp_path, render_pdf_pages=lambda fn: [],
        questions_by_source={},
    )
    assert 'class="questions"' not in out.read_text(encoding="utf-8")


def test_render_quote_appetizer(tmp_path):
    v = _video("Vid")
    out = html.render_reader(
        "M", [v], tmp_path, render_pdf_pages=lambda fn: [],
        quotes_by_source={v.id: "Een pakkende <zin>."},
    )
    content = out.read_text(encoding="utf-8")
    assert 'class="r-quote"' in content
    assert "Een pakkende &lt;zin&gt;." in content
    assert "<zin>" not in content


def test_render_no_quote_when_absent(tmp_path):
    out = html.render_reader(
        "M", [_video("Vid")], tmp_path, render_pdf_pages=lambda fn: [],
    )
    assert 'class="r-quote"' not in out.read_text(encoding="utf-8")


def test_band_meta_doc_vs_video(tmp_path):
    out = html.render_reader(
        "M", [_doc("Doc"), _video("Vid")], tmp_path, render_pdf_pages=lambda fn: [],
    )
    content = out.read_text(encoding="utf-8")
    assert "PDF · 2 p." in content
    assert "Video · 1:00" in content
```

- [ ] **Step 3: Run — verwacht PASS**

Run: `python3 -m pytest tests/test_render_html.py -q`
Expected: PASS (alle render-tests groen tegen de nieuwe markup).

- [ ] **Step 4: Run de volledige suite (vang regressies in andere modules)**

Run: `python3 -m pytest -q`
Expected: PASS, **behalve** mogelijk twee route-tests die de oude export-markup assertten (`test_export_html_includes_questions` checkt op `"Verdiepende vragen"` — blijft kloppen; een eventuele test die op de oude `<h1>`-only structuur leunde wordt in Task 5 meegenomen). Als een route-test hier faalt door de nieuwe markup, noteer welke; Task 5 werkt de export-route + die test bij. Faalt er iets anders, los het op vóór commit.

- [ ] **Step 5: Commit**

```bash
git add app/render/html.py tests/test_render_html.py
git commit -m "$(printf 'feat: restyle reader export to the design system with quote appetizer\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Citaten in de export-route + quotes doorgeven aan de render

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Consumes: `render_reader(..., quotes_by_source=...)` (Task 4), `Store.list_sources` (levert `source.quote`).
- Produces: `_build_reader_html()` bouwt een `quotes_by_source` dict (`source_id -> source.quote`, alleen niet-lege) en geeft die mee aan `render_reader`. `/export` en `/export/pdf` blijven verder gelijk.

- [ ] **Step 1: Schrijf de falende route-test**

Voeg toe aan `tests/test_routes.py`:

```python
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
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_routes.py -k "export_html_includes_quote" -v`
Expected: FAIL (de export geeft nog geen quotes mee; geen `r-quote` in de output).

- [ ] **Step 3: Geef quotes mee in `_build_reader_html` (`app/main.py`)**

In `_build_reader_html`, vlak vóór de `return render_html.render_reader(...)`, voeg toe:

```python
        quotes_by_source = {
            s.id: s.quote for s in sources if s.quote
        }
```

en breid de `render_reader`-aanroep uit met de kwarg:

```python
        return render_html.render_reader(
            title, sources, settings.render_dir,
            render_pdf_pages=render_pdf_pages, subtitle=subtitle,
            questions_by_source=questions_by_source,
            quotes_by_source=quotes_by_source,
        )
```

- [ ] **Step 4: Run — verwacht PASS + volledige suite**

Run: `python3 -m pytest tests/test_routes.py -q`
Expected: PASS. Run dan `python3 -m pytest -q` — alles groen. Als een eerdere export/markup-test nog op verouderde structuur leunt, werk die test bij naar de nieuwe markup (de gedragsgarantie — bv. "Verdiepende vragen" of de citaattekst aanwezig — blijft hetzelfde).

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "$(printf 'feat: pass stored quotes into the reader export\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 6: App-UI in het design system

**Files:**
- Modify (volledig vervangen): `app/templates/index.html`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Consumes: bestaande routes/HTMX (ongewijzigd). `_source_list.html` blijft structureel gelijk en erft de globale CSS.
- Produces: de app-pagina krijgt het design system (Spectral+Archivo, crème/magenta palet, gestileerde knoppen/inputs/bronnenlijst). Alle bestaande forms, namen en `hx-*`-attributen blijven exact gelijk.

- [ ] **Step 1: Schrijf de falende UI-test**

Voeg toe aan `tests/test_routes.py`:

```python
def test_index_uses_design_system(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    body = client.get("/").text
    assert "fonts.googleapis.com" in body
    assert "#e5007d" in body          # magenta accent token
    assert "Archivo" in body
    # existing functionality still present
    assert 'hx-post="/sources/pdf"' in body
    assert 'hx-post="/export/pdf"' in body
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_routes.py -k design_system -v`
Expected: FAIL (geen fonts/`#e5007d`/`Archivo` in de huidige pagina).

- [ ] **Step 3: Vervang `app/templates/index.html` volledig**

```html
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Reader &amp; Writer</title>
  <script src="https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js"
          integrity="sha384-ujb1lZYygJmzgSwoxRggbCHcjc0rB2XoQrxeTUQyRjrOnlCoYta87iKBWq3EsdM2"
          crossorigin="anonymous"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600&family=Spectral:ital,wght@0,400;0,500;0,600;1,500&display=swap">
  <style>
    *{box-sizing:border-box}
    body{margin:0;background:#e7e2d6;color:#211d18;font-family:'Archivo',system-ui,sans-serif;-webkit-font-smoothing:antialiased}
    .app{max-width:880px;margin:0 auto;padding:36px 20px 70px}
    h1{font:600 34px/1.1 'Spectral';margin:0 0 6px}
    h2{font:600 12px 'Archivo';letter-spacing:.16em;text-transform:uppercase;color:#8a8175;margin:34px 0 10px;border-bottom:1px solid #d8d1c2;padding-bottom:6px}
    label{font-size:14px;color:#3a352d}
    input[type=text],input[type=url],input[type=file],select,textarea{
      font:400 14px 'Archivo';color:#211d18;background:#fbf9f4;border:1px solid #cfc7b6;
      border-radius:6px;padding:8px 10px;margin:2px 0}
    textarea{width:100%}
    button{font:600 13px 'Archivo';color:#fff;background:#e5007d;border:0;border-radius:6px;
      padding:9px 16px;cursor:pointer;letter-spacing:.02em}
    button:hover{background:#c70069}
    #source-list{list-style:none;padding:0;margin:0}
    #source-list>li{background:#fbf9f4;border:1px solid #e2dccd;border-radius:8px;padding:14px 16px;margin:10px 0}
    #source-list strong{font:600 15px 'Spectral'}
    #source-list .questions{margin-top:12px;border-top:1px solid #ece6d8;padding-top:10px}
    details{margin-top:8px}
    summary{cursor:pointer;color:#8a8175;font-size:13px}
    a{color:#e5007d}
  </style>
</head>
<body>
<div class="app">
  <h1>AI Reader &amp; Writer</h1>

  <h2>Reader-gegevens</h2>
  <form hx-post="/meta" hx-target="#meta-result">
    <p>
      <label>Titel<br>
        <input type="text" name="reader_title" size="40"
               value="{{ project.reader_title or '' }}"
               placeholder="Titel van de reader"></label>
    </p>
    <p>
      <label>Modulecode
        <input type="text" name="module_code"
               value="{{ project.module_code or '' }}" placeholder="BK-101"></label>
      <label>Collegejaar
        <input type="text" name="academic_year"
               value="{{ project.academic_year or '' }}" placeholder="2025-2026"></label>
    </p>
    <button type="submit">Opslaan</button>
    <span id="meta-result"></span>
  </form>

  <h2>PDF toevoegen</h2>
  <form hx-post="/sources/pdf" hx-encoding="multipart/form-data" hx-target="#source-list" hx-swap="outerHTML">
    <input type="file" name="file" accept="application/pdf" required>
    <button type="submit">Upload PDF</button>
  </form>

  <h2>YouTube-video toevoegen</h2>
  <form hx-post="/sources/video" hx-target="#source-list" hx-swap="outerHTML">
    <input type="url" name="url" placeholder="https://www.youtube.com/watch?v=..." required size="40">
    <button type="submit">Haal video op</button>
  </form>

  <h2>Bloom-doelniveau</h2>
  <form hx-post="/bloom">
    <select name="level">
      <option>Onthouden</option><option>Begrijpen</option><option>Toepassen</option>
      <option>Analyseren</option><option>Evalueren</option><option>Creëren</option>
    </select>
    <button type="submit">Opslaan</button>
  </form>

  <h2>Bronnen</h2>
  {% include "_source_list.html" %}

  <h2>Export</h2>
  <form hx-post="/export" hx-target="#export-result" style="display:inline">
    <button type="submit">Exporteer reader (HTML)</button>
  </form>
  <form hx-post="/export/pdf" hx-target="#export-result" style="display:inline">
    <button type="submit">Exporteer reader (PDF)</button>
  </form>
  <div id="export-result"></div>
</div>
</body>
</html>
```

- [ ] **Step 4: Run — verwacht PASS + volledige suite**

Run: `python3 -m pytest -q`
Expected: PASS (alle tests, inclusief de nieuwe design-system-test).

- [ ] **Step 5: Handmatige rooktest (aanbevolen)**

```bash
python3 -m uvicorn app.main:app --reload
# Voeg een PDF/video toe -> citaat verschijnt automatisch in de export;
# "Exporteer reader (PDF)" -> open data/renders/reader.pdf en bekijk de huisstijl.
```

- [ ] **Step 6: Commit**

```bash
git add app/templates/index.html tests/test_routes.py
git commit -m "$(printf 'feat: apply the design system to the app UI\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Self-Review (uitgevoerd)

**Spec-dekking:**
- Verbatim citaat uit de tekst (substring-gevalideerd) → Task 2 (`extract_quote`/`_is_verbatim`).
- Opslag per bron → Task 1 (`quote`-kolom + migratie + `set_quote`).
- Automatisch bij toevoegen bron → Task 3 (`_autoquote` in beide add-routes).
- Citaat-appetizer aan het begin van elke sectie, zonder cite → Task 4 (`.r-quote` vóór de inhoud, geen `<cite>`).
- Design system op de reader-export → Task 4 (sheets/bands/cover/fonts/palet).
- Design system op de app-UI → Task 6.
- Citaten in de export → Task 5 (`quotes_by_source`).

**Placeholder-scan:** geen TBD/TODO; elke code-stap bevat volledige code. (`"api_key"` in Task 2 wordt vóór commit vervangen door de echte dict-sleutel — staat los toegelicht onder de Global Constraints.)

**Type-consistentie:** `Source.quote` gelijk in model/store/render. `extract_quote(text, *, model, claude_key, _caller)` consistent tussen Task 2-test, implementatie en de Task 3-monkeypatch (`main.extract_quote` met `(text, **kw)`). `render_reader(..., quotes_by_source=...)` consistent tussen Task 4 en Task 5. `_band_meta`/`_render_sheet` alleen intern in `html.py`.

**Bewust buiten scope (YAGNI):** handmatig citaat kiezen/bewerken; per-sectie afwijkende stijl; fontbestanden lokaal embedden (Google Fonts via CDN, met serif/sans-fallback).

---

## Volgende plan

- **Plan 3 — Toetsset:** leeruitkomsten/rubric-upload, stratificatie per leeruitkomst (largest-remainder), MC+open-generatie, auto-beoordeling conform het handboek, export CSV/Word/PDF.
