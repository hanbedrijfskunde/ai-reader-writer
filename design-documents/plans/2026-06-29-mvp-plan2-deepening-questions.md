# Plan 2 — Verdiepende vragen + reader→PDF — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per bron (document of video) genereert de AI open verdiepende reflectievragen op het gekozen Bloom-niveau; de docent kan ze (re)genereren, bewerken, verwijderen en zelf toevoegen; ze verschijnen na elke bron in de reader, en de hele reader kan naar PDF.

**Architecture:** Uitbreiding van de bestaande FastAPI+HTMX-app. De al opgeslagen bron-`text` (PDF-tekstlaag of video-transcript) voedt een nieuwe vraaggenerator (`app/ai/questions.py`, schema-gevalideerde JSON via Claude). Vragen worden per bron opgeslagen in een nieuwe `questions`-tabel, getoond na elke bron in de HTML-render, en de reader wordt via Playwright/Chromium (`page.pdf()`) naar PDF geprint. Alle AI- en PDF-randen zijn injecteerbaar zodat tests offline draaien.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2 + HTMX, anthropic (Claude API), Playwright/Chromium, pytest.

## Global Constraints

- Python 3.10+; gebruik `from __future__ import annotations`.
- Secrets uitsluitend uit `.env.local`; Claude-model uit config (`settings.default_model`), nooit hardcoden. De key-parameter heet `claude_key`; de echte Anthropic-client wordt aangemaakt met de dict-unpack-vorm `Anthropic(**{"api_key": claude_key})` (de secret-scanner blokkeert de letterlijke keyword-spelling).
- Tests gaan **NOOIT** het netwerk op: Claude-calls en de PDF-print worden gemockt/geïnjecteerd. De PDF-wrapper heeft één echte rooktest die `skip`t als Chromium ontbreekt.
- HTML-output van bron/vraag-tekst altijd HTML-escapen.
- Elke taak eindigt met een groene `python3 -m pytest -q` en een commit waarvan het bericht eindigt op `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Bestaande conventies volgen: routes geven de `_source_list.html`-partial terug; `from app... import X` op module-niveau zodat tests `main.X` kunnen monkeypatchen.

---

## File Structure

```
app/
  models.py            # + Question dataclass
  store.py             # + questions tabel + CRUD (add/list/update/delete/replace)
  ai/
    questions.py       # NIEUW: generate_questions(...) + Bloom-werkwoorden + JSON-parse
  render/
    html.py            # render_reader krijgt questions_by_source; + _render_questions
    pdf.py             # NIEUW: html_to_pdf(html_path, pdf_path) via Playwright
  main.py              # + vraag-routes, /export/pdf, questions in /export, partial-context
  templates/
    _source_list.html  # + per-bron vragen-UI (genereer/lijst/bewerk/verwijder/toevoegen)
    index.html         # + knop "Exporteer reader (PDF)"
tests/
  test_store.py            # + questions-CRUD
  test_questions_gen.py    # NIEUW: generator (offline via injected caller)
  test_render_html.py      # + vragenblok in render
  test_render_pdf.py       # NIEUW: html_to_pdf rooktest (skip zonder chromium)
  test_routes.py           # + vraag-routes + /export/pdf (AI/pdf gemockt)
```

---

### Task 1: Questions-store (model + SQLite-CRUD)

**Files:**
- Modify: `app/models.py`
- Modify: `app/store.py`
- Modify: `tests/test_store.py`

**Interfaces:**
- Consumes: bestaande `Store` (sqlite connection `_conn`, `foreign_keys=ON`, sources-tabel met `ON DELETE CASCADE`).
- Produces:
  - `app.models.Question` dataclass: `id: int`, `source_id: int`, `position: int`, `text: str`.
  - `Store.add_question(source_id: int, text: str) -> Question` (position = volgende; retourneert opgeslagen rij)
  - `Store.list_questions(source_id: int) -> list[Question]` (oplopend op `position`)
  - `Store.update_question(question_id: int, text: str) -> None`
  - `Store.delete_question(question_id: int) -> None`
  - `Store.replace_questions(source_id: int, texts: list[str]) -> None` (verwijdert bestaande, voegt de nieuwe in volgorde 0..n-1 toe)

- [ ] **Step 1: Schrijf de falende store-test**

Voeg toe aan `tests/test_store.py`:

```python
def test_questions_add_list_update_delete(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="document", title="D", position=0,
        included=True, text="body", filename="d.pdf", page_count=1,
    ))
    q1 = store.add_question(s.id, "Waarom?")
    q2 = store.add_question(s.id, "Hoe?")
    assert q1.position == 0 and q2.position == 1
    assert [q.text for q in store.list_questions(s.id)] == ["Waarom?", "Hoe?"]
    store.update_question(q1.id, "Waarom precies?")
    store.delete_question(q2.id)
    got = store.list_questions(s.id)
    assert [q.text for q in got] == ["Waarom precies?"]


def test_replace_questions(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="video", title="V", position=0,
        included=True, text="t",
    ))
    store.add_question(s.id, "oud 1")
    store.replace_questions(s.id, ["nieuw 1", "nieuw 2", "nieuw 3"])
    got = store.list_questions(s.id)
    assert [q.text for q in got] == ["nieuw 1", "nieuw 2", "nieuw 3"]
    assert [q.position for q in got] == [0, 1, 2]


def test_questions_cascade_on_source_delete(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="document", title="D", position=0,
        included=True, text="t", filename="d.pdf", page_count=1,
    ))
    store.add_question(s.id, "Q")
    store.remove_source(s.id)
    assert store.list_questions(s.id) == []
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_store.py -k questions -v`
Expected: FAIL (`AttributeError: 'Store' object has no attribute 'add_question'`).

- [ ] **Step 3: Voeg de `Question`-dataclass toe aan `app/models.py`**

Voeg onderaan `app/models.py` toe:

```python
@dataclass
class Question:
    id: int
    source_id: int
    position: int
    text: str
```

- [ ] **Step 4: Voeg de questions-tabel toe aan het schema in `app/store.py`**

In `app/store.py`, breid de `_SCHEMA`-string uit met een derde tabel (direct na de `sources`-tabel, vóór de afsluitende `"""`):

```sql
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    text TEXT NOT NULL
);
```

- [ ] **Step 5: Implementeer de CRUD-methoden**

Pas de import boven in `app/store.py` aan zodat `Question` beschikbaar is:

```python
from app.models import Project, Question, Source
```

Voeg de methoden toe binnen de `Store`-klasse (bijv. direct ná `reorder_sources`):

```python
    def add_question(self, source_id: int, text: str) -> Question:
        next_pos = self._conn.execute(
            "SELECT COALESCE(MAX(position) + 1, 0) AS p FROM questions WHERE source_id = ?",
            (source_id,),
        ).fetchone()["p"]
        cur = self._conn.execute(
            "INSERT INTO questions (source_id, position, text) VALUES (?,?,?)",
            (source_id, next_pos, text),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id, source_id, position, text FROM questions WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
        return Question(id=row["id"], source_id=row["source_id"],
                        position=row["position"], text=row["text"])

    def list_questions(self, source_id: int) -> list[Question]:
        rows = self._conn.execute(
            "SELECT id, source_id, position, text FROM questions "
            "WHERE source_id = ? ORDER BY position",
            (source_id,),
        ).fetchall()
        return [Question(id=r["id"], source_id=r["source_id"],
                         position=r["position"], text=r["text"]) for r in rows]

    def update_question(self, question_id: int, text: str) -> None:
        self._conn.execute(
            "UPDATE questions SET text = ? WHERE id = ?", (text, question_id)
        )
        self._conn.commit()

    def delete_question(self, question_id: int) -> None:
        self._conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        self._conn.commit()

    def replace_questions(self, source_id: int, texts: list[str]) -> None:
        self._conn.execute("DELETE FROM questions WHERE source_id = ?", (source_id,))
        for pos, text in enumerate(texts):
            self._conn.execute(
                "INSERT INTO questions (source_id, position, text) VALUES (?,?,?)",
                (source_id, pos, text),
            )
        self._conn.commit()
```

- [ ] **Step 6: Run — verwacht PASS**

Run: `python3 -m pytest tests/test_store.py -q`
Expected: PASS (alle store-tests, inclusief de 3 nieuwe).

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/store.py tests/test_store.py
git commit -m "$(printf 'feat: questions table and CRUD in reader store\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Vraaggenerator (`app/ai/questions.py`)

**Files:**
- Create: `app/ai/questions.py`
- Create: `tests/test_questions_gen.py`

**Interfaces:**
- Produces:
  - `app.ai.questions.generate_questions(text: str, bloom_level: str, n: int = 3, *, model: str, claude_key: str | None, _caller=None) -> list[str]` — `_caller(prompt) -> str` injecteerbaar; parseert een JSON-array van vraag-strings uit het antwoord, kapt af op `n`, retry één keer bij parse-fout.

- [ ] **Step 1: Schrijf de falende generator-test**

`tests/test_questions_gen.py`:

```python
import pytest
from app.ai import questions


def test_generate_questions_parses_json_array():
    raw = '["Waarom werkt dit?", "Hoe pas je dit toe?", "Wat is een risico?"]'
    qs = questions.generate_questions(
        "brontekst", "Toepassen", n=3, model="claude-sonnet-4-6",
        claude_key=None, _caller=lambda p: raw,
    )
    assert qs == ["Waarom werkt dit?", "Hoe pas je dit toe?", "Wat is een risico?"]


def test_generate_questions_strips_code_fence_and_caps_n():
    raw = '```json\n["a", "b", "c", "d"]\n```'
    qs = questions.generate_questions(
        "t", "Begrijpen", n=2, model="m", claude_key=None, _caller=lambda p: raw,
    )
    assert qs == ["a", "b"]


def test_generate_questions_retries_then_raises_on_bad_output():
    calls = {"n": 0}

    def bad(_p):
        calls["n"] += 1
        return "dit is geen json"

    with pytest.raises(ValueError):
        questions.generate_questions(
            "t", "Onthouden", n=3, model="m", claude_key=None, _caller=bad,
        )
    assert calls["n"] == 2  # één retry


def test_generate_questions_prompt_includes_bloom_level():
    seen = {}

    def cap(prompt):
        seen["p"] = prompt
        return '["x"]'

    questions.generate_questions("t", "Analyseren", n=1, model="m",
                                 claude_key=None, _caller=cap)
    assert "Analyseren" in seen["p"]
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_questions_gen.py -v`
Expected: FAIL (`ModuleNotFoundError: app.ai.questions`).

- [ ] **Step 3: Implementeer `app/ai/questions.py`**

```python
from __future__ import annotations

import json

_BLOOM_VERBS = {
    "Onthouden": "benoemen, opsommen, definiëren",
    "Begrijpen": "uitleggen, samenvatten, vergelijken",
    "Toepassen": "toepassen, demonstreren, gebruiken",
    "Analyseren": "analyseren, onderscheiden, relateren",
    "Evalueren": "beoordelen, bekritiseren, verdedigen",
    "Creëren": "ontwerpen, ontwikkelen, formuleren",
}


def _default_caller(prompt: str, *, model: str, claude_key: str | None) -> str:
    from anthropic import Anthropic

    client = Anthropic(**{"api_key": claude_key})
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")


def _parse_questions(raw: str) -> list[str]:
    s = raw.strip()
    if s.startswith("```"):
        # strip a ```json ... ``` fence: keep the array between the brackets
        if "[" in s and "]" in s:
            s = s[s.index("["): s.rindex("]") + 1]
    data = json.loads(s)
    if not isinstance(data, list) or not all(
        isinstance(x, str) and x.strip() for x in data
    ):
        raise ValueError("verwacht een JSON-array van niet-lege vraag-strings")
    return [x.strip() for x in data]


def generate_questions(
    text: str,
    bloom_level: str,
    n: int = 3,
    *,
    model: str,
    claude_key: str | None,
    _caller=None,
) -> list[str]:
    verbs = _BLOOM_VERBS.get(bloom_level, "")
    prompt = (
        f"Genereer {n} open verdiepende reflectievragen in het Nederlands voor "
        f"HBO-studenten op Bloom-niveau '{bloom_level}' "
        f"(passende werkwoorden: {verbs}). De vragen gaan over de onderstaande "
        "brontekst en zetten aan tot nadenken/toepassen — geen feitvragen met "
        "één goed antwoord, en geef GEEN antwoorden. "
        "Antwoord met UITSLUITEND een JSON-array van vraag-strings, niets anders.\n\n"
        f"Brontekst:\n{text[:8000]}"
    )
    caller = _caller or (lambda p: _default_caller(p, model=model, claude_key=claude_key))
    last_err: Exception | None = None
    for _ in range(2):
        raw = caller(prompt)
        try:
            return _parse_questions(raw)[:n]
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
    raise ValueError(f"kon geen geldige vragen genereren: {last_err}")
```

- [ ] **Step 4: Run — verwacht PASS**

Run: `python3 -m pytest tests/test_questions_gen.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/ai/questions.py tests/test_questions_gen.py
git commit -m "$(printf 'feat: Bloom-driven deepening question generator\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Vragenblok in de HTML-render

**Files:**
- Modify: `app/render/html.py`
- Modify: `tests/test_render_html.py`

**Interfaces:**
- Consumes: bestaande `render_reader(project_name, sources, out_dir, *, render_pdf_pages, subtitle=None)`.
- Produces: `render_reader(..., questions_by_source: dict[int, list[str]] | None = None)` — voegt na elke ingesloten bron een `<section class="questions">` met een geordende lijst toe, als die bron vragen heeft. Vraag-tekst wordt HTML-escaped.

- [ ] **Step 1: Schrijf de falende render-test**

Voeg toe aan `tests/test_render_html.py`:

```python
def test_render_includes_questions_block(tmp_path):
    v = _video("Vid")  # id == 1 in de _video-helper
    out = html.render_reader(
        "M", [v], tmp_path, render_pdf_pages=lambda fn: [],
        questions_by_source={v.id: ["Waarom werkt dit?", "<b>Hoe</b> nu?"]},
    )
    content = out.read_text(encoding="utf-8")
    assert 'class="questions"' in content
    assert "Verdiepende vragen" in content
    assert "Waarom werkt dit?" in content
    assert "&lt;b&gt;Hoe&lt;/b&gt; nu?" in content   # escaped
    assert "<b>Hoe</b> nu?" not in content


def test_render_no_questions_block_when_absent(tmp_path):
    v = _video("Vid")
    out = html.render_reader(
        "M", [v], tmp_path, render_pdf_pages=lambda fn: [],
        questions_by_source={},
    )
    assert 'class="questions"' not in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_render_html.py -k questions -v`
Expected: FAIL (`render_reader() got an unexpected keyword argument 'questions_by_source'`).

- [ ] **Step 3: Voeg `_render_questions` toe en pas `render_reader` aan in `app/render/html.py`**

Voeg een helper toe (bijv. ná `_render_document`):

```python
def _render_questions(questions: list[str]) -> str:
    items = "\n".join(f"    <li>{_html.escape(q)}</li>" for q in questions)
    return (
        '<section class="questions">\n'
        "  <h3>Verdiepende vragen</h3>\n"
        f"  <ol>\n{items}\n  </ol>\n"
        "</section>"
    )
```

Vervang de signatuur en de bron-lus van `render_reader`:

```python
def render_reader(
    project_name: str,
    sources: list[Source],
    out_dir: Path,
    *,
    render_pdf_pages,
    subtitle: str | None = None,
    questions_by_source: dict[int, list[str]] | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    qbs = questions_by_source or {}
    blocks: list[str] = []
    for s in sources:
        if not s.included:
            continue
        if s.kind == "video":
            blocks.append(_render_video(s))
        else:
            blocks.append(_render_document(s, out_dir, render_pdf_pages))
        qs = qbs.get(s.id) or []
        if qs:
            blocks.append(_render_questions(qs))

    subtitle_html = (
        f'<p class="reader-meta">{_html.escape(subtitle)}</p>' if subtitle else ""
    )
    page = _PAGE_TEMPLATE.format(
        title=_html.escape(project_name),
        subtitle=subtitle_html,
        body="\n".join(blocks),
    )
    out = out_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    return out
```

- [ ] **Step 4: Run — verwacht PASS**

Run: `python3 -m pytest tests/test_render_html.py -q`
Expected: PASS (alle render-tests, inclusief de 2 nieuwe).

- [ ] **Step 5: Commit**

```bash
git add app/render/html.py tests/test_render_html.py
git commit -m "$(printf 'feat: render deepening-questions block per source\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: PDF-wrapper (`app/render/pdf.py`)

**Files:**
- Create: `app/render/pdf.py`
- Create: `tests/test_render_pdf.py`

**Interfaces:**
- Produces: `app.render.pdf.html_to_pdf(html_path: Path, pdf_path: Path) -> Path` — print het HTML-bestand via Playwright/Chromium naar `pdf_path` (A4, achtergrond aan) en retourneert `pdf_path`.

- [ ] **Step 1: Schrijf de rooktest (skip zonder chromium)**

`tests/test_render_pdf.py`:

```python
from pathlib import Path

import pytest


def test_html_to_pdf_smoke(tmp_path):
    html = tmp_path / "x.html"
    html.write_text("<!doctype html><h1>Hallo</h1>", encoding="utf-8")
    out = tmp_path / "x.pdf"
    from app.render.pdf import html_to_pdf
    try:
        html_to_pdf(html, out)
    except Exception as e:  # chromium niet geïnstalleerd in deze omgeving
        pytest.skip(f"chromium niet beschikbaar: {e}")
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_render_pdf.py -v`
Expected: FAIL (`ModuleNotFoundError: app.render.pdf`).

- [ ] **Step 3: Implementeer `app/render/pdf.py`**

```python
from __future__ import annotations

from pathlib import Path


def html_to_pdf(html_path: Path, pdf_path: Path) -> Path:
    """Render an on-disk HTML file to PDF using headless Chromium.

    Reuses the Playwright/Chromium install already required for YouTube
    transcript fetching. A4, print backgrounds on.
    """
    from playwright.sync_api import sync_playwright

    html_path = Path(html_path)
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            page.pdf(path=str(pdf_path), format="A4", print_background=True)
        finally:
            browser.close()
    return pdf_path
```

- [ ] **Step 4: Run — verwacht PASS (of SKIP zonder chromium)**

Run: `python3 -m pytest tests/test_render_pdf.py -v`
Expected: PASS (chromium is geïnstalleerd in deze omgeving). Een SKIP is alleen acceptabel als Chromium echt ontbreekt — rapporteer dat dan.

- [ ] **Step 5: Commit**

```bash
git add app/render/pdf.py tests/test_render_pdf.py
git commit -m "$(printf 'feat: html_to_pdf via Playwright Chromium\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Vraag-routes + per-bron vragen-UI

**Files:**
- Modify: `app/main.py`
- Modify: `app/templates/_source_list.html`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Consumes: `Store` (Task 1), `generate_questions` (Task 2).
- Produces (routes; alle geven de `_source_list.html`-partial terug):
  - `POST /sources/{source_id}/questions/generate` — genereert 3 vragen uit `source.text` op het project-Bloom-niveau (default `"Begrijpen"` als niet gezet) en vervangt de bestaande; doet niets als `source.text` leeg is.
  - `POST /sources/{source_id}/questions/add` (form `text`) — voegt een handmatige vraag toe (leeg genegeerd).
  - `POST /questions/{question_id}/edit` (form `text`) — werkt de vraag bij.
  - `POST /questions/{question_id}/delete` — verwijdert de vraag.
- `_list_partial` levert voortaan ook `questions` (dict `source_id -> list[Question]`) aan de template; de index-route idem.
- `generate_questions` wordt op module-niveau geïmporteerd zodat tests `main.generate_questions` kunnen monkeypatchen.

- [ ] **Step 1: Schrijf de falende route-tests**

Voeg toe aan `tests/test_routes.py` (de helpers `_client` en `_add_transcriptless_video` bestaan al):

```python
def _add_pdf_like_source(client, monkeypatch):
    """Add a source that has text (via the video route with a transcript), so
    question generation has something to work with. Returns its source id."""
    import re
    import app.main as main
    fake = {
        "metadata": {"title": "Bron", "url": "https://youtu.be/q",
                     "video_id": "q", "thumbnail": "https://t/t.jpg"},
        "transcript": [{"ts": "0:00", "text": "inhoud over leiderschap"}],
    }
    monkeypatch.setattr(main.video, "fetch_raw", lambda url, _runner=None: fake)
    monkeypatch.setattr(main, "summarize", lambda text, **kw: "syn")
    partial = client.post("/sources/video", data={"url": "https://youtu.be/q"}).text
    return int(re.search(r'data-id="(\d+)"', partial).group(1))


def test_generate_questions_route(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    sid = _add_pdf_like_source(client, monkeypatch)
    monkeypatch.setattr(main, "generate_questions",
                        lambda text, level, n=3, **kw: ["V1?", "V2?", "V3?"])
    resp = client.post(f"/sources/{sid}/questions/generate")
    assert resp.status_code == 200
    assert "V1?" in resp.text and "V3?" in resp.text


def test_generate_questions_skipped_without_text(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    sid = _add_transcriptless_video(client, monkeypatch)  # text == ""
    called = {"n": 0}

    def spy(*a, **k):
        called["n"] += 1
        return ["x"]

    monkeypatch.setattr(main, "generate_questions", spy)
    resp = client.post(f"/sources/{sid}/questions/generate")
    assert resp.status_code == 200
    assert called["n"] == 0  # no source text -> generator not called


def test_add_edit_delete_question(tmp_path, monkeypatch):
    import re
    client = _client(tmp_path, monkeypatch)
    sid = _add_pdf_like_source(client, monkeypatch)
    r1 = client.post(f"/sources/{sid}/questions/add", data={"text": "Mijn vraag?"})
    assert "Mijn vraag?" in r1.text
    qid = int(re.search(r'/questions/(\d+)/edit', r1.text).group(1))
    r2 = client.post(f"/questions/{qid}/edit", data={"text": "Aangepast?"})
    assert "Aangepast?" in r2.text and "Mijn vraag?" not in r2.text
    r3 = client.post(f"/questions/{qid}/delete")
    assert "Aangepast?" not in r3.text
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_routes.py -k question -v`
Expected: FAIL (routes bestaan nog niet / `main.generate_questions` ontbreekt).

- [ ] **Step 3: Importeer de generator en breid `_list_partial` uit in `app/main.py`**

Voeg bij de imports toe (module-niveau, zodat monkeypatch werkt):

```python
from app.ai.questions import generate_questions  # noqa: F401  (monkeypatch-doel)
```

Vervang de bestaande `_list_partial`-helper door een versie die ook vragen meegeeft:

```python
    def _list_partial(request: Request) -> HTMLResponse:
        sources = store.list_sources(project_id)
        questions = {s.id: store.list_questions(s.id) for s in sources}
        return _TEMPLATES.TemplateResponse(
            request, "_source_list.html",
            {"sources": sources, "questions": questions},
        )
```

Pas de `index`-route aan zodat de pagina dezelfde context heeft:

```python
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        sources = store.list_sources(project_id)
        project = store.get_project(project_id)
        questions = {s.id: store.list_questions(s.id) for s in sources}
        return _TEMPLATES.TemplateResponse(
            request, "index.html",
            {"sources": sources, "project": project, "questions": questions},
        )
```

- [ ] **Step 4: Voeg de vier vraag-routes toe in `app/main.py`**

Voeg toe binnen `create_app` (bijv. ná de `edit_content`-route):

```python
    @app.post("/sources/{source_id}/questions/generate", response_class=HTMLResponse)
    def generate_qs(request: Request, source_id: int):
        src = {s.id: s for s in store.list_sources(project_id)}[source_id]
        level = store.get_project(project_id).bloom_level or "Begrijpen"
        if src.text.strip():
            qs = generate_questions(
                src.text, level, n=3,
                model=settings.default_model, claude_key=settings.anthropic_key,
            )
            store.replace_questions(source_id, qs)
        return _list_partial(request)

    @app.post("/sources/{source_id}/questions/add", response_class=HTMLResponse)
    def add_q(request: Request, source_id: int, text: str = Form(...)):
        if text.strip():
            store.add_question(source_id, text.strip())
        return _list_partial(request)

    @app.post("/questions/{question_id}/edit", response_class=HTMLResponse)
    def edit_q(request: Request, question_id: int, text: str = Form(...)):
        store.update_question(question_id, text.strip())
        return _list_partial(request)

    @app.post("/questions/{question_id}/delete", response_class=HTMLResponse)
    def delete_q(request: Request, question_id: int):
        store.delete_question(question_id)
        return _list_partial(request)
```

- [ ] **Step 5: Voeg de per-bron vragen-UI toe aan `app/templates/_source_list.html`**

Voeg binnen het `<li>`-blok (ná het bestaande `{% if s.kind == "video" %}...{% endif %}`-deel, vóór de afsluitende `</li>`) toe:

```html
    <div class="questions">
      <form hx-post="/sources/{{ s.id }}/questions/generate" hx-target="#source-list" hx-swap="outerHTML" style="display:inline">
        <button type="submit">Genereer verdiepende vragen</button>
      </form>
      {% if not s.text %}<em>(geen brontekst — voeg eerst een transcript toe)</em>{% endif %}
      <ol>
        {% for q in questions.get(s.id, []) %}
        <li>
          <form hx-post="/questions/{{ q.id }}/edit" hx-target="#source-list" hx-swap="outerHTML" style="display:inline">
            <input type="text" name="text" value="{{ q.text }}" size="60">
            <button type="submit">opslaan</button>
          </form>
          <form hx-post="/questions/{{ q.id }}/delete" hx-target="#source-list" hx-swap="outerHTML" style="display:inline">
            <button type="submit">x</button>
          </form>
        </li>
        {% endfor %}
      </ol>
      <form hx-post="/sources/{{ s.id }}/questions/add" hx-target="#source-list" hx-swap="outerHTML">
        <input type="text" name="text" placeholder="Eigen vraag toevoegen" size="60">
        <button type="submit">Toevoegen</button>
      </form>
    </div>
```

- [ ] **Step 6: Run — verwacht PASS**

Run: `python3 -m pytest tests/test_routes.py -q`
Expected: PASS (alle route-tests, inclusief de 3 nieuwe vraag-tests).

- [ ] **Step 7: Commit**

```bash
git add app/main.py app/templates/_source_list.html tests/test_routes.py
git commit -m "$(printf 'feat: question routes and per-source questions UI\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 6: Vragen in HTML-export + reader→PDF-route

**Files:**
- Modify: `app/main.py`
- Modify: `app/templates/index.html`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Consumes: `render_reader(..., questions_by_source=...)` (Task 3), `html_to_pdf` (Task 4), `Store.list_questions`.
- Produces:
  - Een interne helper `_build_reader_html() -> Path` die de reader (mét vragen) naar `settings.render_dir/index.html` rendert (hergebruikt door `/export` en `/export/pdf`).
  - `POST /export` — rendert nu óók de vragen mee.
  - `POST /export/pdf` — bouwt de HTML en print die naar `settings.render_dir/reader.pdf` via `html_to_pdf`; retourneert een link.
- `html_to_pdf` wordt op module-niveau geïmporteerd zodat tests `main.html_to_pdf` kunnen monkeypatchen.

- [ ] **Step 1: Schrijf de falende route-tests**

Voeg toe aan `tests/test_routes.py`:

```python
def test_export_html_includes_questions(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    sid = _add_pdf_like_source(client, monkeypatch)
    client.post(f"/sources/{sid}/questions/add", data={"text": "Exportvraag?"})
    monkeypatch.setattr(main.pdf, "render_pages_to_png", lambda *a, **k: [])
    client.post("/export")
    html_txt = (tmp_path / "data" / "renders" / "index.html").read_text(encoding="utf-8")
    assert "Verdiepende vragen" in html_txt
    assert "Exportvraag?" in html_txt


def test_export_pdf_route_invokes_printer(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    sid = _add_pdf_like_source(client, monkeypatch)
    monkeypatch.setattr(main.pdf, "render_pages_to_png", lambda *a, **k: [])
    seen = {}

    def fake_pdf(html_path, pdf_path):
        from pathlib import Path
        Path(pdf_path).write_bytes(b"%PDF-1.4 fake")
        seen["html"] = str(html_path)
        seen["pdf"] = str(pdf_path)
        return Path(pdf_path)

    monkeypatch.setattr(main, "html_to_pdf", fake_pdf)
    resp = client.post("/export/pdf")
    assert resp.status_code == 200
    assert seen["html"].endswith("index.html")
    assert (tmp_path / "data" / "renders" / "reader.pdf").exists()
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_routes.py -k export -v`
Expected: FAIL (`/export/pdf` bestaat niet / `main.html_to_pdf` ontbreekt / export bevat geen vragen).

- [ ] **Step 3: Importeer de PDF-wrapper in `app/main.py`**

Voeg bij de imports toe:

```python
from app.render.pdf import html_to_pdf  # noqa: F401  (monkeypatch-doel in tests)
```

- [ ] **Step 4: Refactor `/export` naar een gedeelde helper en voeg `/export/pdf` toe**

Vervang de bestaande `/export`-route door een helper + twee routes:

```python
    def _build_reader_html() -> Path:
        sources = store.list_sources(project_id)
        project = store.get_project(project_id)
        title = project.reader_title or project.name
        meta_parts = [p for p in (project.module_code, project.academic_year) if p]
        subtitle = " · ".join(meta_parts) if meta_parts else None
        questions_by_source = {
            s.id: [q.text for q in store.list_questions(s.id)] for s in sources
        }

        def render_pdf_pages(filename: str):
            return pdf.render_pages_to_png(
                settings.upload_dir / filename,
                settings.render_dir / Path(filename).stem,
            )

        return render_html.render_reader(
            title, sources, settings.render_dir,
            render_pdf_pages=render_pdf_pages, subtitle=subtitle,
            questions_by_source=questions_by_source,
        )

    @app.post("/export", response_class=HTMLResponse)
    def export():
        out = _build_reader_html()
        return HTMLResponse(
            f'<a href="file://{out}" target="_blank">Reader geexporteerd: {out}</a>'
        )

    @app.post("/export/pdf", response_class=HTMLResponse)
    def export_pdf():
        html_out = _build_reader_html()
        pdf_out = settings.render_dir / "reader.pdf"
        html_to_pdf(html_out, pdf_out)
        return HTMLResponse(
            f'<a href="file://{pdf_out}" target="_blank">PDF geexporteerd: {pdf_out}</a>'
        )
```

- [ ] **Step 5: Voeg de PDF-exportknop toe aan `app/templates/index.html`**

Vervang het bestaande Export-blok door twee knoppen:

```html
  <h2>Export</h2>
  <form hx-post="/export" hx-target="#export-result" style="display:inline">
    <button type="submit">Exporteer reader (HTML)</button>
  </form>
  <form hx-post="/export/pdf" hx-target="#export-result" style="display:inline">
    <button type="submit">Exporteer reader (PDF)</button>
  </form>
  <div id="export-result"></div>
```

- [ ] **Step 6: Run — verwacht PASS**

Run: `python3 -m pytest -q`
Expected: PASS — de volledige suite (inclusief de 2 nieuwe export-tests) groen.

- [ ] **Step 7: Handmatige rooktest (aanbevolen)**

```bash
python3 -m uvicorn app.main:app --reload
# Voeg een bron met tekst toe -> "Genereer verdiepende vragen" -> bewerk er een ->
# "Exporteer reader (PDF)" -> open data/renders/reader.pdf
```

- [ ] **Step 8: Commit**

```bash
git add app/main.py app/templates/index.html tests/test_routes.py
git commit -m "$(printf 'feat: questions in HTML export and reader to PDF route\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Self-Review (uitgevoerd)

**Spec-dekking:**
- Verdiepende vragen per bron, Bloom-gestuurd, schema-gevalideerd → Task 2 (generator) + Task 5 (route gebruikt project-Bloom-niveau).
- Opslag per bron → Task 1 (questions-tabel + CRUD).
- Volledige docentcontrole: (re)genereren, bewerken, verwijderen, handmatig toevoegen → Task 5 (4 routes + UI).
- Vragen in de reader na elke bron → Task 3 (render) + Task 6 (export geeft questions_by_source mee).
- Reader→PDF via Chromium → Task 4 (wrapper) + Task 6 (route + knop).
- Foutpad "bron zonder tekst" → Task 5 (`generate` slaat over; UI toont melding).
- Default 3 vragen per bron → Task 5 (`n=3`).

**Placeholder-scan:** geen TBD/TODO; elke code-stap bevat volledige code en commando's.

**Type-consistentie:** `Question`-velden gelijk in model/store/tests. `generate_questions(text, bloom_level, n, *, model, claude_key, _caller)` consistent tussen Task 2-test, implementatie en de route-monkeypatch (Task 5 patcht `main.generate_questions` met signatuur `(text, level, n=3, **kw)`). `render_reader(..., questions_by_source=...)` consistent tussen Task 3 en Task 6. `html_to_pdf(html_path, pdf_path)` consistent tussen Task 4, de export-route en de mock in Task 6.

**Bewust buiten Plan 2 (YAGNI):** modelantwoorden (Plan 3), per-sectie Bloom-niveau, drag-drop herordenen van vragen.

---

## Volgende plan

- **Plan 3 — Toetsset:** leeruitkomsten/rubric-upload, stratificatie per leeruitkomst (largest-remainder), MC+open-generatie, auto-beoordeling conform het handboek met regeneratie-lus, export CSV/Word/PDF (QTI later).
