# Plan 1 — Reader-pijplijn (walking skeleton) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Een docent voegt via een lokale webUI bronnen toe (PDF-uploads en YouTube-URL's), ziet ze samengevoegd in één reader die hij kan herordenen/verwijderen, en exporteert die reader als zelfstandige HTML.

**Architecture:** Lokale FastAPI-app met een HTMX-frontend. Elke bron wordt opgeslagen in een SQLite "Reader Store". PDF's worden met PyMuPDF per pagina naar PNG gerenderd (verbatim weergave); YouTube-video's worden via de gevendorde youtube-transcript-skill (Playwright) opgehaald en met Claude tot een synopsis verwerkt. De HTML-export voegt de ingesloten bronnen in volgorde samen. Verdiepende vragen en toetsset zijn latere plannen.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, Jinja2 + HTMX, PyMuPDF (fitz), anthropic (Claude API), Playwright (via gevendorde skill), pytest.

## Global Constraints

- Python 3.10+ (gebruik `from __future__ import annotations` voor `list[...]`/`dict[...]`-typehints).
- Secrets uitsluitend uit `.env.local` (al in `.gitignore`); nooit committen.
- Auteursrechtelijk lesmateriaal (`source-docs/`) staat in `.gitignore`; geuploade bestanden gaan naar een gitignored `data/`-map.
- Claude-model komt uit config (`DEFAULT_MODEL`, default `claude-sonnet-4-6`); nooit hardcoden in businesslogica.
- Tests gaan **nooit** het netwerk op: YouTube-ophaling en Claude-calls worden gemockt; PDF-tests draaien op de echte sample-PDF's in `source-docs/`.
- Elke taak eindigt met een groene testrun en een commit.
- Commitberichten eindigen met de Co-Authored-By-regel uit de repo-conventie.

---

## File Structure

```
ai-reader-writer/
  requirements.txt
  .env.local.example            # template (committed); echte .env.local is gitignored
  app/
    __init__.py
    config.py                   # Settings: laadt .env.local, DEFAULT_MODEL, paden
    main.py                     # FastAPI-app + routes
    models.py                   # dataclasses: Project, Source
    store.py                    # SQLite Reader Store (CRUD)
    ingest/
      __init__.py
      pdf.py                    # PyMuPDF: page_count, extract_text, render_pages_to_png
      video.py                  # wrapper rond gevendorde skill + synopsis
    ai/
      __init__.py
      client.py                 # thin Claude-wrapper (synopsis)
    render/
      __init__.py
      html.py                   # reader-model -> zelfstandige HTML
    integrations/
      youtube_transcript/       # GEVENDORDE skill (kopie uit ai-wiki)
    templates/
      index.html
      _source_list.html
  data/                         # GITIGNORED: SQLite-db, uploads, render-output
  tests/
    __init__.py
    conftest.py
    fixtures/
      sample_video.json
      sample_video_no_transcript.json
    test_config.py
    test_store.py
    test_pdf_ingest.py
    test_video_ingest.py
    test_render_html.py
    test_routes.py
```

---

### Task 1: Projectscaffolding, config & FastAPI-skeleton

**Files:**
- Create: `requirements.txt`
- Create: `.env.local.example`
- Create: `app/__init__.py` (leeg)
- Create: `app/config.py`
- Create: `app/main.py`
- Create: `tests/__init__.py` (leeg)
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`
- Create: `tests/test_routes.py`
- Modify: `.gitignore` (voeg `data/` toe)

**Interfaces:**
- Produces:
  - `app.config.Settings` dataclass: `anthropic_key`, `default_model`, `data_dir`, `db_path`, `upload_dir`, `render_dir`.
  - `app.config.load_settings(env_file=None, data_dir=None) -> Settings`
  - `app.main.create_app() -> fastapi.FastAPI` met route `GET /health` -> `{"status": "ok"}`.

- [ ] **Step 1: Voeg `data/` toe aan `.gitignore`**

Voeg onderaan `.gitignore` toe:

```
# Lokale runtime-data (db, uploads, renders)
data/
```

- [ ] **Step 2: Schrijf `requirements.txt`**

```
fastapi>=0.110
uvicorn[standard]>=0.29
jinja2>=3.1
python-multipart>=0.0.9
pymupdf>=1.24
anthropic>=0.39
playwright>=1.40
PyYAML>=6.0
pytest>=8.0
httpx>=0.27
```

- [ ] **Step 3: Schrijf `.env.local.example`**

```
# Kopieer naar .env.local en vul je eigen sleutel in. .env.local staat in .gitignore.
ANTHROPIC_API_KEY=PLAATS_HIER_JE_ANTHROPIC_SLEUTEL
DEFAULT_MODEL=claude-sonnet-4-6
```

- [ ] **Step 4: Schrijf de falende config-test**

`tests/test_config.py`:

```python
from app.config import load_settings


def test_load_settings_reads_env_file(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text("ANTHROPIC_API_KEY=dummy-value\nDEFAULT_MODEL=claude-haiku-4-5\n")
    settings = load_settings(env_file=env, data_dir=tmp_path / "data")
    assert settings.anthropic_key == "dummy-value"
    assert settings.default_model == "claude-haiku-4-5"
    assert settings.db_path == tmp_path / "data" / "reader.sqlite"


def test_load_settings_defaults_model_when_absent(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text("ANTHROPIC_API_KEY=dummy-value\n")
    settings = load_settings(env_file=env, data_dir=tmp_path / "data")
    assert settings.default_model == "claude-sonnet-4-6"
```

- [ ] **Step 5: Run de test — verwacht FAIL**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: app.config`).

- [ ] **Step 6: Implementeer `app/config.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    anthropic_key: str | None
    default_model: str
    data_dir: Path
    db_path: Path
    upload_dir: Path
    render_dir: Path


def _parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        out[name.strip()] = value.strip()
    return out


def load_settings(env_file: Path | None = None, data_dir: Path | None = None) -> Settings:
    root = Path(__file__).resolve().parent.parent
    env_file = env_file or (root / ".env.local")
    data_dir = data_dir or (root / "data")

    values: dict[str, str] = {}
    if env_file.exists():
        values = _parse_env(env_file.read_text(encoding="utf-8"))

    upload_dir = data_dir / "uploads"
    render_dir = data_dir / "renders"
    for d in (data_dir, upload_dir, render_dir):
        d.mkdir(parents=True, exist_ok=True)

    return Settings(
        anthropic_key=values.get("ANTHROPIC_API_KEY") or None,
        default_model=values.get("DEFAULT_MODEL", "claude-sonnet-4-6"),
        data_dir=data_dir,
        db_path=data_dir / "reader.sqlite",
        upload_dir=upload_dir,
        render_dir=render_dir,
    )
```

- [ ] **Step 7: Run de config-test — verwacht PASS**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 8: Schrijf de falende route-test**

`tests/conftest.py`:

```python
import pytest


@pytest.fixture
def sample_pdf_dir():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "source-docs"
```

`tests/test_routes.py`:

```python
from fastapi.testclient import TestClient
from app.main import create_app


def test_health_endpoint():
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 9: Run de route-test — verwacht FAIL**

Run: `python -m pytest tests/test_routes.py -v`
Expected: FAIL (`ModuleNotFoundError: app.main`).

- [ ] **Step 10: Implementeer `app/main.py`**

```python
from __future__ import annotations

from fastapi import FastAPI

from app.config import load_settings


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="AI Reader & Writer")
    app.state.settings = settings

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 11: Run de route-test — verwacht PASS**

Run: `python -m pytest tests/test_routes.py -v`
Expected: PASS (1 passed).

- [ ] **Step 12: Commit**

```bash
git add requirements.txt .env.local.example .gitignore app/ tests/
git commit -m "$(printf 'feat: scaffold FastAPI app with config loader\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Reader Store (SQLite) — projecten en bronnen

**Files:**
- Create: `app/models.py`
- Create: `app/store.py`
- Create: `tests/test_store.py`

**Interfaces:**
- Produces:
  - `app.models.Source` dataclass: `id`, `project_id`, `kind` (`"document"`|`"video"`), `title`, `position`, `included`, `text`, en optioneel `filename`, `page_count`, `youtube_url`, `video_id`, `channel`, `duration`, `thumbnail_url`, `synopsis`.
  - `app.models.Project` dataclass: `id`, `name`, `status` (`"concept"`|`"definitief"`), `bloom_level`.
  - `app.store.Store(db_path)` met: `create_project(name) -> Project`, `get_project(id) -> Project`, `set_status(id, status)`, `set_bloom_level(id, level)`, `add_source(project_id, source) -> Source` (kent zelf `position` toe), `list_sources(project_id) -> list[Source]` (oplopend op `position`), `set_included(source_id, included)`, `remove_source(source_id)`, `reorder_sources(project_id, ordered_ids)`.

- [ ] **Step 1: Schrijf de falende store-test**

`tests/test_store.py`:

```python
from app.models import Source
from app.store import Store


def _doc(title: str) -> Source:
    return Source(
        id=0, project_id=0, kind="document", title=title,
        position=0, included=True, text="body",
        filename=f"{title}.pdf", page_count=3,
    )


def test_create_and_get_project(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("Module A")
    assert p.id > 0
    assert p.status == "concept"
    assert store.get_project(p.id).name == "Module A"


def test_add_and_list_sources_orders_by_position(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    a = store.add_source(p.id, _doc("a"))
    b = store.add_source(p.id, _doc("b"))
    assert a.position == 0 and b.position == 1
    assert [s.title for s in store.list_sources(p.id)] == ["a", "b"]


def test_reorder_sources(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    a = store.add_source(p.id, _doc("a"))
    b = store.add_source(p.id, _doc("b"))
    store.reorder_sources(p.id, [b.id, a.id])
    assert [s.title for s in store.list_sources(p.id)] == ["b", "a"]


def test_set_included_and_remove(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    a = store.add_source(p.id, _doc("a"))
    store.set_included(a.id, False)
    assert store.list_sources(p.id)[0].included is False
    store.remove_source(a.id)
    assert store.list_sources(p.id) == []


def test_set_status_and_bloom(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    store.set_status(p.id, "definitief")
    store.set_bloom_level(p.id, "Analyseren")
    got = store.get_project(p.id)
    assert got.status == "definitief"
    assert got.bloom_level == "Analyseren"
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python -m pytest tests/test_store.py -v`
Expected: FAIL (`ModuleNotFoundError: app.models`).

- [ ] **Step 3: Implementeer `app/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Project:
    id: int
    name: str
    status: str = "concept"
    bloom_level: str | None = None


@dataclass
class Source:
    id: int
    project_id: int
    kind: str  # "document" | "video"
    title: str
    position: int
    included: bool
    text: str
    filename: str | None = None
    page_count: int | None = None
    youtube_url: str | None = None
    video_id: str | None = None
    channel: str | None = None
    duration: str | None = None
    thumbnail_url: str | None = None
    synopsis: str | None = None
```

- [ ] **Step 4: Implementeer `app/store.py`**

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.models import Project, Source

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'concept',
    bloom_level TEXT
);
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    position INTEGER NOT NULL,
    included INTEGER NOT NULL DEFAULT 1,
    text TEXT NOT NULL DEFAULT '',
    filename TEXT,
    page_count INTEGER,
    youtube_url TEXT,
    video_id TEXT,
    channel TEXT,
    duration TEXT,
    thumbnail_url TEXT,
    synopsis TEXT
);
"""

_SOURCE_COLS = [
    "id", "project_id", "kind", "title", "position", "included", "text",
    "filename", "page_count", "youtube_url", "video_id", "channel",
    "duration", "thumbnail_url", "synopsis",
]


class Store:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def create_project(self, name: str) -> Project:
        cur = self._conn.execute("INSERT INTO projects (name) VALUES (?)", (name,))
        self._conn.commit()
        return self.get_project(int(cur.lastrowid))

    def get_project(self, project_id: int) -> Project:
        row = self._conn.execute(
            "SELECT id, name, status, bloom_level FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"project {project_id} not found")
        return Project(id=row["id"], name=row["name"], status=row["status"],
                       bloom_level=row["bloom_level"])

    def set_status(self, project_id: int, status: str) -> None:
        self._conn.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
        self._conn.commit()

    def set_bloom_level(self, project_id: int, level: str) -> None:
        self._conn.execute("UPDATE projects SET bloom_level = ? WHERE id = ?", (level, project_id))
        self._conn.commit()

    def _row_to_source(self, row: sqlite3.Row) -> Source:
        data = {k: row[k] for k in _SOURCE_COLS}
        data["included"] = bool(data["included"])
        return Source(**data)

    def add_source(self, project_id: int, source: Source) -> Source:
        next_pos = self._conn.execute(
            "SELECT COALESCE(MAX(position) + 1, 0) AS p FROM sources WHERE project_id = ?",
            (project_id,),
        ).fetchone()["p"]
        cur = self._conn.execute(
            """INSERT INTO sources
               (project_id, kind, title, position, included, text, filename,
                page_count, youtube_url, video_id, channel, duration,
                thumbnail_url, synopsis)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (project_id, source.kind, source.title, next_pos,
             int(source.included), source.text, source.filename,
             source.page_count, source.youtube_url, source.video_id,
             source.channel, source.duration, source.thumbnail_url,
             source.synopsis),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM sources WHERE id = ?", (int(cur.lastrowid),)
        ).fetchone()
        return self._row_to_source(row)

    def list_sources(self, project_id: int) -> list[Source]:
        rows = self._conn.execute(
            "SELECT * FROM sources WHERE project_id = ? ORDER BY position",
            (project_id,),
        ).fetchall()
        return [self._row_to_source(r) for r in rows]

    def set_included(self, source_id: int, included: bool) -> None:
        self._conn.execute(
            "UPDATE sources SET included = ? WHERE id = ?", (int(included), source_id)
        )
        self._conn.commit()

    def remove_source(self, source_id: int) -> None:
        self._conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        self._conn.commit()

    def reorder_sources(self, project_id: int, ordered_ids: list[int]) -> None:
        for pos, sid in enumerate(ordered_ids):
            self._conn.execute(
                "UPDATE sources SET position = ? WHERE id = ? AND project_id = ?",
                (pos, sid, project_id),
            )
        self._conn.commit()
```

- [ ] **Step 5: Run — verwacht PASS**

Run: `python -m pytest tests/test_store.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/store.py tests/test_store.py
git commit -m "$(printf 'feat: add SQLite reader store for projects and sources\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: PDF-ingest met PyMuPDF

**Files:**
- Create: `app/ingest/__init__.py` (leeg)
- Create: `app/ingest/pdf.py`
- Create: `tests/test_pdf_ingest.py`

**Interfaces:**
- Produces:
  - `app.ingest.pdf.page_count(pdf_path) -> int`
  - `app.ingest.pdf.extract_text(pdf_path) -> str` (pagina's gescheiden door `\n\n`)
  - `app.ingest.pdf.has_text_layer(pdf_path) -> bool`
  - `app.ingest.pdf.render_pages_to_png(pdf_path, out_dir, dpi=144) -> list[Path]` (`page-0001.png` ...)

- [ ] **Step 1: Schrijf de falende PDF-test**

`tests/test_pdf_ingest.py`:

```python
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
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python -m pytest tests/test_pdf_ingest.py -v`
Expected: FAIL (`ModuleNotFoundError: app.ingest.pdf`).

- [ ] **Step 3: Implementeer `app/ingest/pdf.py`**

```python
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def page_count(pdf_path: Path) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def extract_text(pdf_path: Path) -> str:
    parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n\n".join(parts).strip()


def has_text_layer(pdf_path: Path) -> bool:
    with fitz.open(pdf_path) as doc:
        for page in doc:
            if page.get_text("text").strip():
                return True
    return False


def render_pages_to_png(pdf_path: Path, out_dir: Path, dpi: int = 144) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            out = out_dir / f"page-{i:04d}.png"
            pix.save(out)
            out_paths.append(out)
    return out_paths
```

- [ ] **Step 4: Run — verwacht PASS**

Run: `python -m pytest tests/test_pdf_ingest.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/ingest/__init__.py app/ingest/pdf.py tests/test_pdf_ingest.py
git commit -m "$(printf 'feat: add PDF ingest (text + page rendering) via PyMuPDF\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: YouTube-ingest — gevendorde skill + synopsis

**Files:**
- Create: `app/integrations/youtube_transcript/` (kopie van de skill)
- Create: `app/ai/__init__.py` (leeg)
- Create: `app/ai/client.py`
- Create: `app/ingest/video.py`
- Create: `tests/fixtures/sample_video.json`
- Create: `tests/fixtures/sample_video_no_transcript.json`
- Create: `tests/test_video_ingest.py`

**Interfaces:**
- Produces:
  - `app.ai.client.summarize(transcript, *, model, claude_key, max_words=120, _caller=None) -> str` — `_caller(prompt) -> str` injecteerbaar voor tests.
  - `app.ingest.video.fetch_raw(url, _runner=None) -> dict` — `_runner(url) -> dict` injecteerbaar.
  - `app.ingest.video.transcript_text(raw) -> str`
  - `app.ingest.video.build_source(url, *, model, claude_key, _runner=None, _summarizer=None) -> Source`

- [ ] **Step 1: Vendor de skill in de repo**

```bash
mkdir -p app/integrations/youtube_transcript
cp "/Users/witoldtenhove/Projects/ai-wiki/.claude/skills/youtube-transcript-skill/fetch_transcript.py" app/integrations/youtube_transcript/
cp "/Users/witoldtenhove/Projects/ai-wiki/.claude/skills/youtube-transcript-skill/requirements.txt" app/integrations/youtube_transcript/
touch app/integrations/__init__.py app/integrations/youtube_transcript/__init__.py
printf '# Gevendord uit ai-wiki/.claude/skills/youtube-transcript-skill\n# Playwright-gebaseerde YouTube transcript+metadata fetcher.\n' > app/integrations/youtube_transcript/PROVENANCE.md
```

- [ ] **Step 2: Maak de JSON-fixtures**

`tests/fixtures/sample_video.json`:

```json
{
  "metadata": {
    "title": "Wat is leiderschap?",
    "video_id": "abc123XYZ_0",
    "url": "https://www.youtube.com/watch?v=abc123XYZ_0",
    "channel": "HAN Bedrijfskunde",
    "duration": "12:34",
    "length_seconds": 754,
    "thumbnail": "https://i.ytimg.com/vi/abc123XYZ_0/maxresdefault.jpg"
  },
  "transcript": [
    {"ts": "0:00", "text": "Welkom bij deze les over leiderschap."},
    {"ts": "0:05", "text": "We bespreken drie kernstijlen."}
  ]
}
```

`tests/fixtures/sample_video_no_transcript.json`:

```json
{
  "metadata": {
    "title": "Muziekclip zonder ondertitels",
    "video_id": "noCaps00000",
    "url": "https://www.youtube.com/watch?v=noCaps00000",
    "channel": "Some Channel",
    "duration": "3:01",
    "length_seconds": 181,
    "thumbnail": "https://i.ytimg.com/vi/noCaps00000/maxresdefault.jpg"
  },
  "transcript": [],
  "error": "no transcript section"
}
```

- [ ] **Step 3: Schrijf de falende video-test**

`tests/test_video_ingest.py`:

```python
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
```

- [ ] **Step 4: Run — verwacht FAIL**

Run: `python -m pytest tests/test_video_ingest.py -v`
Expected: FAIL (`ModuleNotFoundError: app.ingest.video`).

- [ ] **Step 5: Implementeer `app/ai/client.py`**

```python
from __future__ import annotations


def _default_caller(prompt: str, *, model: str, claude_key: str | None) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=claude_key)
    msg = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")


def summarize(
    transcript: str,
    *,
    model: str,
    claude_key: str | None,
    max_words: int = 120,
    _caller=None,
) -> str:
    prompt = (
        "Vat het volgende videotranscript samen in een heldere Nederlandse "
        f"synopsis van maximaal {max_words} woorden voor HBO-studenten. "
        "Geef alleen de synopsis, geen inleiding.\n\n"
        f"Transcript:\n{transcript}"
    )
    caller = _caller or (lambda p: _default_caller(p, model=model, claude_key=claude_key))
    return caller(prompt).strip()
```

- [ ] **Step 6: Implementeer `app/ingest/video.py`**

```python
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
```

- [ ] **Step 7: Run — verwacht PASS**

Run: `python -m pytest tests/test_video_ingest.py -v`
Expected: PASS (4 passed).

- [ ] **Step 8: Commit**

```bash
git add app/integrations app/ai app/ingest/video.py tests/fixtures tests/test_video_ingest.py
git commit -m "$(printf 'feat: add YouTube ingest with vendored transcript skill and synopsis\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Reader-HTML-export

**Files:**
- Create: `app/render/__init__.py` (leeg)
- Create: `app/render/html.py`
- Create: `tests/test_render_html.py`

**Interfaces:**
- Produces:
  - `app.render.html.render_reader(project_name, sources, out_dir, *, render_pdf_pages) -> Path` — schrijft `out_dir/index.html`; `render_pdf_pages(filename) -> list[Path]` injecteerbaar; alleen `included` bronnen, in volgorde; documenten als `<img>`-pagina's, video's als thumbnail-link + synopsis.

- [ ] **Step 1: Schrijf de falende render-test**

`tests/test_render_html.py`:

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
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python -m pytest tests/test_render_html.py -v`
Expected: FAIL (`ModuleNotFoundError: app.render.html`).

- [ ] **Step 3: Implementeer `app/render/html.py`**

```python
from __future__ import annotations

import html as _html
from pathlib import Path

from app.models import Source

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
    url = _html.escape(s.youtube_url or "")
    thumb = _html.escape(s.thumbnail_url or "")
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
        rel = _copy_into(Path(p), out_dir).name
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
```

- [ ] **Step 4: Run — verwacht PASS**

Run: `python -m pytest tests/test_render_html.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/render tests/test_render_html.py
git commit -m "$(printf 'feat: render reader to standalone HTML (pages + video blocks)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 6: Webfrontend (HTMX) — bronnen toevoegen, ordenen, exporteren

**Files:**
- Modify: `app/main.py`
- Create: `app/templates/index.html`
- Create: `app/templates/_source_list.html`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Consumes: `app.store.Store`, `app.ingest.pdf`, `app.ingest.video`, `app.ai.client.summarize`, `app.render.html.render_reader`, `app.config.load_settings`.
- Produces routes: `GET /`, `POST /sources/pdf`, `POST /sources/video`, `POST /sources/reorder`, `POST /sources/{id}/toggle`, `POST /sources/{id}/delete`, `POST /bloom`, `POST /export`. Eén impliciet project (aangemaakt bij opstart als de db leeg is).

- [ ] **Step 1: Schrijf de falende routetest (uitbreiding)**

Voeg toe aan `tests/test_routes.py`:

```python
def _client(tmp_path, monkeypatch):
    from app.config import load_settings
    import app.main as main

    settings = load_settings(env_file=tmp_path / "none.env", data_dir=tmp_path / "data")
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    return TestClient(main.create_app())


def test_index_renders(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Reader" in resp.text


def test_add_video_lists_source(tmp_path, monkeypatch):
    import app.main as main
    fake = {
        "metadata": {"title": "Mijn video", "url": "https://youtu.be/x",
                     "video_id": "x", "channel": "C", "duration": "1:00",
                     "thumbnail": "https://t/thumb.jpg"},
        "transcript": [{"ts": "0:00", "text": "hallo wereld"}],
    }
    monkeypatch.setattr(main.video, "fetch_raw", lambda url, _runner=None: fake)
    monkeypatch.setattr(main, "summarize", lambda text, **kw: "Synopsis.")
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/sources/video", data={"url": "https://youtu.be/x"})
    assert resp.status_code == 200
    assert "Mijn video" in resp.text


def test_add_pdf_lists_source(tmp_path, monkeypatch, sample_pdf_dir):
    import pytest
    pdf_file = sample_pdf_dir / "Over leiderschap_DIG.pdf"
    if not pdf_file.exists():
        pytest.skip("sample PDF ontbreekt")
    client = _client(tmp_path, monkeypatch)
    with pdf_file.open("rb") as fh:
        resp = client.post(
            "/sources/pdf",
            files={"file": ("Over leiderschap_DIG.pdf", fh, "application/pdf")},
        )
    assert resp.status_code == 200
    assert "Over leiderschap" in resp.text
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python -m pytest tests/test_routes.py -v`
Expected: FAIL (geen `/` route / `main.video` ontbreekt).

- [ ] **Step 3: Schrijf `app/templates/_source_list.html`**

```html
<ul id="source-list">
  {% for s in sources %}
  <li data-id="{{ s.id }}">
    <strong>{{ s.title }}</strong> <span>({{ s.kind }})</span>
    <form hx-post="/sources/{{ s.id }}/toggle" hx-target="#source-list" hx-swap="outerHTML" style="display:inline">
      <button type="submit">{{ "in reader" if s.included else "verborgen" }}</button>
    </form>
    <form hx-post="/sources/{{ s.id }}/delete" hx-target="#source-list" hx-swap="outerHTML" style="display:inline">
      <button type="submit">verwijder</button>
    </form>
  </li>
  {% endfor %}
</ul>
```

- [ ] **Step 4: Schrijf `app/templates/index.html`**

```html
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>AI Reader &amp; Writer</title>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <style>body{font-family:system-ui,sans-serif;max-width:800px;margin:2rem auto}</style>
</head>
<body>
  <h1>AI Reader &amp; Writer</h1>

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
      <option>Analyseren</option><option>Evalueren</option><option>Creeren</option>
    </select>
    <button type="submit">Opslaan</button>
  </form>

  <h2>Bronnen</h2>
  {% include "_source_list.html" %}

  <h2>Export</h2>
  <form hx-post="/export" hx-target="#export-result">
    <button type="submit">Exporteer reader (HTML)</button>
  </form>
  <div id="export-result"></div>
</body>
</html>
```

- [ ] **Step 5: Vervang de inhoud van `app/main.py`**

```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import load_settings
from app.ingest import pdf, video
from app.ai.client import summarize  # noqa: F401  (monkeypatch-doel in tests)
from app.models import Source
from app.render import html as render_html
from app.store import Store

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def create_app() -> FastAPI:
    settings = load_settings()
    store = Store(settings.db_path)

    existing = store._conn.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()
    project_id = existing["id"] if existing else store.create_project("Mijn reader").id

    app = FastAPI(title="AI Reader & Writer")
    app.state.settings = settings
    app.state.store = store
    app.state.project_id = project_id

    def _list_partial(request: Request) -> HTMLResponse:
        sources = store.list_sources(project_id)
        return _TEMPLATES.TemplateResponse(
            "_source_list.html", {"request": request, "sources": sources}
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        sources = store.list_sources(project_id)
        return _TEMPLATES.TemplateResponse(
            "index.html", {"request": request, "sources": sources}
        )

    @app.post("/sources/pdf", response_class=HTMLResponse)
    async def add_pdf(request: Request, file: UploadFile = File(...)):
        dest = settings.upload_dir / file.filename
        dest.write_bytes(await file.read())
        src = Source(
            id=0, project_id=project_id, kind="document",
            title=Path(file.filename).stem, position=0, included=True,
            text=pdf.extract_text(dest), filename=file.filename,
            page_count=pdf.page_count(dest),
        )
        store.add_source(project_id, src)
        return _list_partial(request)

    @app.post("/sources/video", response_class=HTMLResponse)
    def add_video(request: Request, url: str = Form(...)):
        raw = video.fetch_raw(url)
        meta = raw.get("metadata") or {}
        text = video.transcript_text(raw)
        synopsis = (
            summarize(text, model=settings.default_model, claude_key=settings.anthropic_key)
            if text else None
        )
        src = Source(
            id=0, project_id=project_id, kind="video",
            title=meta.get("title") or url, position=0, included=True,
            text=text, youtube_url=meta.get("url") or url,
            video_id=meta.get("video_id"), channel=meta.get("channel"),
            duration=meta.get("duration"), thumbnail_url=meta.get("thumbnail"),
            synopsis=synopsis,
        )
        store.add_source(project_id, src)
        return _list_partial(request)

    @app.post("/sources/reorder", response_class=HTMLResponse)
    def reorder(request: Request, ordered_ids: str = Form(...)):
        ids = [int(x) for x in ordered_ids.split(",") if x.strip()]
        store.reorder_sources(project_id, ids)
        return _list_partial(request)

    @app.post("/sources/{source_id}/toggle", response_class=HTMLResponse)
    def toggle(request: Request, source_id: int):
        current = {s.id: s for s in store.list_sources(project_id)}[source_id]
        store.set_included(source_id, not current.included)
        return _list_partial(request)

    @app.post("/sources/{source_id}/delete", response_class=HTMLResponse)
    def delete(request: Request, source_id: int):
        store.remove_source(source_id)
        return _list_partial(request)

    @app.post("/bloom")
    def set_bloom(level: str = Form(...)):
        store.set_bloom_level(project_id, level)
        return {"status": "ok", "level": level}

    @app.post("/export", response_class=HTMLResponse)
    def export():
        sources = store.list_sources(project_id)
        project = store.get_project(project_id)

        def render_pdf_pages(filename: str):
            return pdf.render_pages_to_png(settings.upload_dir / filename, settings.render_dir)

        out = render_html.render_reader(
            project.name, sources, settings.render_dir, render_pdf_pages=render_pdf_pages
        )
        return HTMLResponse(
            f'<a href="file://{out}" target="_blank">Reader geexporteerd: {out}</a>'
        )

    return app


app = create_app()
```

- [ ] **Step 6: Run de routetests — verwacht PASS**

Run: `python -m pytest tests/test_routes.py -v`
Expected: PASS (4 passed; `test_add_pdf_lists_source` skipt als de sample-PDF ontbreekt).

- [ ] **Step 7: Run de volledige suite**

Run: `python -m pytest -v`
Expected: alle tests PASS/SKIP, geen failures.

- [ ] **Step 8: Handmatige rooktest (aanbevolen)**

```bash
python -m playwright install chromium   # eenmalig, voor echte video-ophaling
python -m uvicorn app.main:app --reload
# Open http://127.0.0.1:8000/ , upload een PDF, plak een YouTube-URL, klik Export.
```

- [ ] **Step 9: Commit**

```bash
git add app/main.py app/templates tests/test_routes.py
git commit -m "$(printf 'feat: HTMX frontend to add, order and export reader sources\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Self-Review (uitgevoerd)

**Spec-dekking (Plan 1-scope):**
- Bronnen samenvoegen (D1) -> Task 2 + Task 5 + Task 6.
- Verbatim PDF-weergave (D2) -> Task 3 (`render_pages_to_png`) + Task 5 (page-`<img>`).
- Video-integratie (D2b) -> Task 4 (ingest + synopsis) + Task 5 (thumbnail+link).
- Verwijderen/herordenen op bronniveau -> Task 2 + Task 6.
- Bloom-niveau kiezen (opslag) -> Task 2 + Task 6. Vraaggeneratie = Plan 2.
- Reader -> HTML-export -> Task 5 + Task 6.
- Foutpad "video zonder transcript" -> Task 4 (`build_source` zonder synopsis).
- **Bewust buiten Plan 1:** verdiepende vragen (Plan 2), toetsset + PDF-export (Plan 2/3), drag-drop reorder-UI (de `/sources/reorder`-route bestaat al; de JS-interactie is een verfijning).

**Placeholder-scan:** geen TBD/TODO; elke code-stap bevat volledige code en commando's.

**Type-consistentie:** `Source`/`Project`-velden identiek in store, ingest, render en routes. `render_pdf_pages(filename) -> list[Path]` consistent tussen render-test, implementatie en route-closure. `summarize(...)`/`build_source(...)`-signaturen (met `claude_key`) consistent tussen Task 4 en Task 6.

---

## Volgende plannen

- **Plan 2 — Verdiepende vragen:** `app/ai/questions.py` (Bloom-gestuurde generatie per bron, schema-gevalideerd), review/edit-UI, vraagblokken in de reader, reader->PDF-export.
- **Plan 3 — Toetsset:** LU/rubric-upload + parsing, stratificatie per leeruitkomst (largest-remainder), MC+open-generatie, auto-beoordeling conform handboek met regeneratie-lus, export CSV/Word/PDF.
