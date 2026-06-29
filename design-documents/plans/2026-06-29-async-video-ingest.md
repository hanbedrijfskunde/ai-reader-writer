# Asynchrone video-ingest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Een YouTube-video toevoegen reageert direct: de bron verschijnt meteen met de status "bezig met ophalen…", en het trage transcript-ophalen + synopsis + citaat gebeurt op de achtergrond; de bronnenlijst ververst zichzelf tot de video klaar is.

**Architecture:** De trage Playwright-fetch (tot ~136s) wordt van het HTTP-verzoek afgehaald. `POST /sources/video` voegt direct een video-bron toe met `processing=True` + placeholdertitel en plant een FastAPI `BackgroundTask` (`process_video`) die `fetch_raw`+`summarize`+`extract_quote` doet en de bron bijwerkt. De `_source_list.html`-partial pollt elke 2s (`hx-get="/sources"`) zolang er een bron `processing` is.

**Tech Stack:** Python 3.10+, FastAPI (BackgroundTasks), Jinja2 + HTMX, SQLite, pytest.

## Global Constraints

- Python 3.10+; `from __future__ import annotations`.
- Tests gaan **NOOIT** het netwerk op: `video.fetch_raw`, `summarize`, `extract_quote` worden gemockt; de achtergrondtaak draait in de TestClient synchroon ná het endpoint, dus mocks die vóór de POST gezet zijn gelden ook voor de achtergrondtaak.
- Claude-model uit `settings.default_model`, key `settings.anthropic_key`, nooit hardcoden.
- `process_video` staat op **module-niveau** in `app/main.py` (patchbaar als `main.process_video`) en gebruikt de module-globals `video`/`summarize`/`extract_quote` (patchbaar).
- Routes geven de `_source_list.html`-partial terug.
- Elke taak eindigt met een groene `python3 -m pytest -q` en een commit eindigend op `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Gebruik `python3 -m pytest`.

---

## File Structure

```
app/
  models.py            # + Source.processing: bool = False
  store.py             # + processing-kolom + migratie + bool-conversie + finish_video()
  main.py              # add_video -> direct toevoegen + BackgroundTask; module-level process_video; GET /sources; any_processing in partial/index
  templates/
    _source_list.html  # processing-rij + conditionele 2s-polling op de <ul>
tests/
  test_store.py        # + processing migratie + finish_video
  test_routes.py       # + async add_video gedrag, process_video unit, GET /sources, UI; bijgewerkte video-tests
```

---

### Task 1: Store — `processing`-kolom + `finish_video`

**Files:**
- Modify: `app/models.py`
- Modify: `app/store.py`
- Modify: `tests/test_store.py`

**Interfaces:**
- Produces:
  - `app.models.Source.processing: bool = False` (laatste veld, ná `quote`).
  - sources-tabel krijgt `processing INTEGER NOT NULL DEFAULT 0`; bestaande DB's gemigreerd; `_row_to_source` zet `processing` om naar `bool`.
  - `Store.finish_video(source_id, *, title, video_id=None, channel=None, duration=None, thumbnail_url=None, text="", synopsis=None, quote=None) -> None` — zet alle videovelden én `processing=0` in één UPDATE.

- [ ] **Step 1: Schrijf de falende store-test**

Voeg toe aan `tests/test_store.py`:

```python
def test_processing_migration_and_finish_video(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="video", title="Video wordt opgehaald…",
        position=0, included=True, text="", youtube_url="https://y/x",
        processing=True,
    ))
    assert store.list_sources(p.id)[0].processing is True
    store.finish_video(
        s.id, title="Echte titel", video_id="x", channel="Ch",
        duration="1:00", thumbnail_url="https://t/t.jpg",
        text="transcript", synopsis="syn", quote="een citaat",
    )
    got = store.list_sources(p.id)[0]
    assert got.processing is False
    assert got.title == "Echte titel"
    assert got.synopsis == "syn"
    assert got.quote == "een citaat"
    assert got.text == "transcript"
    assert got.thumbnail_url == "https://t/t.jpg"


def test_finish_video_failure_path(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="video", title="Video wordt opgehaald…",
        position=0, included=True, text="", processing=True,
    ))
    store.finish_video(s.id, title="Ophalen mislukt")
    got = store.list_sources(p.id)[0]
    assert got.processing is False and got.title == "Ophalen mislukt"
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_store.py -k "processing or finish_video" -v`
Expected: FAIL (`TypeError: ... 'processing'` of `AttributeError: finish_video`).

- [ ] **Step 3: Voeg `processing` toe aan `app/models.py`**

In de `Source`-dataclass, als laatste veld (ná `quote`):

```python
    processing: bool = False
```

- [ ] **Step 4: Kolom + migratie + bool-conversie + `finish_video` in `app/store.py`**

In `_SCHEMA` sources-tabel, ná `quote TEXT`:

```sql
    quote TEXT,
    processing INTEGER NOT NULL DEFAULT 0
```

Append `"processing"` aan `_SOURCE_COLS`:

```python
    "duration", "thumbnail_url", "synopsis", "quote", "processing",
```

Breid de migratie uit (`_SOURCE_META_COLS`):

```python
    _SOURCE_META_COLS = {"quote": "TEXT", "processing": "INTEGER NOT NULL DEFAULT 0"}
```

In `_row_to_source`, zet ná de `included`-conversie ook `processing` om naar bool:

```python
        data["included"] = bool(data["included"])
        data["processing"] = bool(data["processing"])
```

In `add_source`: neem `processing` mee in de INSERT (de kolomlijst en de waarden). Voeg `processing` toe aan de kolomnamen en `int(source.processing)` aan de VALUES-tuple, naast `synopsis`/`quote`. (De bestaande INSERT zet expliciet alle kolommen — voeg `processing` als laatste toe, vóór de afsluitende `)`; en `int(source.processing)` op dezelfde positie in de waarden.)

Voeg `finish_video` toe binnen de `Store`-klasse (bijv. ná `set_quote`):

```python
    def finish_video(
        self,
        source_id: int,
        *,
        title: str,
        video_id: str | None = None,
        channel: str | None = None,
        duration: str | None = None,
        thumbnail_url: str | None = None,
        text: str = "",
        synopsis: str | None = None,
        quote: str | None = None,
    ) -> None:
        self._conn.execute(
            "UPDATE sources SET title = ?, video_id = ?, channel = ?, duration = ?, "
            "thumbnail_url = ?, text = ?, synopsis = ?, quote = ?, processing = 0 "
            "WHERE id = ?",
            (title, video_id, channel, duration, thumbnail_url, text,
             synopsis, quote, source_id),
        )
        self._conn.commit()
```

- [ ] **Step 5: Run — verwacht PASS**

Run: `python3 -m pytest tests/test_store.py -q`
Expected: PASS (alle store-tests; de bestaande `test_set_quote_roundtrip` e.d. blijven groen omdat `processing` default 0/False is).

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/store.py tests/test_store.py
git commit -m "$(printf 'feat: processing flag on source and finish_video updater\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Module-level `process_video` (achtergrondpijplijn)

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Consumes: `Store.finish_video` (Task 1), de module-globals `video`, `summarize`, `extract_quote` in `app/main.py`, `settings`.
- Produces: `app.main.process_video(store, settings, source_id: int, url: str) -> None` op MODULE-niveau (buiten `create_app`). Haalt transcript op, maakt synopsis (als er tekst is) en een verbatim citaat (als er tekst is), en roept `store.finish_video(...)` aan. Bij élke uitzondering: `store.finish_video(source_id, title="Ophalen mislukt")`.

- [ ] **Step 1: Schrijf de falende unit-tests**

Voeg toe aan `tests/test_routes.py`:

```python
def test_process_video_success(tmp_path, monkeypatch):
    import app.main as main
    from app.config import load_settings
    from app.store import Store
    from app.models import Source

    settings = load_settings(env_file=tmp_path / "none.env", data_dir=tmp_path / "data")
    store = Store(settings.db_path)
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="video", title="Video wordt opgehaald…",
        position=0, included=True, text="", youtube_url="https://youtu.be/x",
        processing=True,
    ))
    fake = {"metadata": {"title": "Echte titel", "url": "https://youtu.be/x",
                          "video_id": "x", "thumbnail": "https://t/t.jpg"},
            "transcript": [{"ts": "0:00", "text": "inhoud over leiderschap"}]}
    monkeypatch.setattr(main.video, "fetch_raw", lambda url, _runner=None: fake)
    monkeypatch.setattr(main, "summarize", lambda text, **kw: "syn")
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "inhoud over leiderschap")

    main.process_video(store, settings, s.id, "https://youtu.be/x")

    got = store.list_sources(p.id)[0]
    assert got.processing is False
    assert got.title == "Echte titel"
    assert got.synopsis == "syn"
    assert got.quote == "inhoud over leiderschap"


def test_process_video_failure_sets_failed_title(tmp_path, monkeypatch):
    import app.main as main
    from app.config import load_settings
    from app.store import Store
    from app.models import Source

    settings = load_settings(env_file=tmp_path / "none.env", data_dir=tmp_path / "data")
    store = Store(settings.db_path)
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="video", title="Video wordt opgehaald…",
        position=0, included=True, text="", processing=True,
    ))

    def boom(url, _runner=None):
        raise RuntimeError("playwright kapot")

    monkeypatch.setattr(main.video, "fetch_raw", boom)
    main.process_video(store, settings, s.id, "https://youtu.be/x")

    got = store.list_sources(p.id)[0]
    assert got.processing is False and got.title == "Ophalen mislukt"
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_routes.py -k process_video -v`
Expected: FAIL (`AttributeError: module 'app.main' has no attribute 'process_video'`).

- [ ] **Step 3: Voeg `process_video` op module-niveau toe in `app/main.py`**

Voeg toe ná de imports en vóór `def create_app()` (zo blijft het patchbaar als `main.process_video`):

```python
def process_video(store: "Store", settings, source_id: int, url: str) -> None:
    """Background task: fetch transcript, summarise, extract a verbatim quote,
    then update the pending source. Any failure leaves a clear failed title."""
    try:
        raw = video.fetch_raw(url)
        meta = raw.get("metadata") or {}
        text = video.transcript_text(raw)
        synopsis = (
            summarize(text, model=settings.default_model, claude_key=settings.anthropic_key)
            if text else None
        )
        quote = (
            extract_quote(text, model=settings.default_model, claude_key=settings.anthropic_key)
            if text else ""
        )
        store.finish_video(
            source_id,
            title=meta.get("title") or url,
            video_id=meta.get("video_id"),
            channel=meta.get("channel"),
            duration=meta.get("duration"),
            thumbnail_url=meta.get("thumbnail"),
            text=text,
            synopsis=synopsis,
            quote=quote or None,
        )
    except Exception:
        store.finish_video(source_id, title="Ophalen mislukt")
```

(`summarize`, `extract_quote`, `video` zijn al op module-niveau geïmporteerd.)

- [ ] **Step 4: Run — verwacht PASS**

Run: `python3 -m pytest tests/test_routes.py -k process_video -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "$(printf 'feat: module-level process_video background pipeline\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: `add_video` async + `GET /sources` + testupdates

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Consumes: `process_video` (Task 2), `BackgroundTasks`.
- Produces:
  - `POST /sources/video` voegt **direct** een video-bron toe (`processing=True`, titel "Video wordt opgehaald…", `youtube_url=url`, `text=""`), plant `background_tasks.add_task(process_video, store, settings, stored.id, url)`, en geeft de partial direct terug. Geen `fetch_raw`/`summarize`/`extract_quote` meer in de route zelf.
  - `GET /sources` geeft de `_source_list.html`-partial terug (voor polling).
  - `_list_partial` en `index` geven `any_processing` mee (waar als één bron `processing` is).

- [ ] **Step 1: Schrijf/!pas de route-tests aan**

Voeg toe aan `tests/test_routes.py`:

```python
def test_add_video_returns_pending_and_schedules(tmp_path, monkeypatch):
    import re
    import app.main as main
    scheduled = {}

    def fake_process(store, settings, source_id, url):
        scheduled["id"] = source_id
        scheduled["url"] = url  # do NOT process -> source stays pending

    monkeypatch.setattr(main, "process_video", fake_process)
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/sources/video", data={"url": "https://youtu.be/x"})
    assert resp.status_code == 200
    assert "Video wordt opgehaald" in resp.text          # placeholder shown
    sid = int(re.search(r'data-id="(\d+)"', resp.text).group(1))
    assert scheduled == {"id": sid, "url": "https://youtu.be/x"}
    # the source exists and is still processing (background was a no-op)
    src = {s.id: s for s in main_store(client).list_sources(store_project_id(client))}[sid]
    assert src.processing is True


def test_sources_poll_route_returns_list(tmp_path, monkeypatch):
    monkeypatch.setattr(__import__("app.main", fromlist=["x"]), "process_video",
                        lambda *a, **k: None)
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/sources")
    assert resp.status_code == 200
    assert 'id="source-list"' in resp.text
```

Update the existing `test_add_video_lists_source` so it asserts the FINAL state (the background task runs in TestClient after the endpoint; it must mock `extract_quote` too). Replace that test body with:

```python
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
    monkeypatch.setattr(main, "extract_quote", lambda text, **kw: "")
    client = _client(tmp_path, monkeypatch)
    client.post("/sources/video", data={"url": "https://youtu.be/x"})
    # background finished -> the real title now shows in a fresh render
    assert "Mijn video" in client.get("/").text
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_routes.py -k "pending or poll or add_video_lists" -v`
Expected: FAIL (route nog synchroon; `GET /sources` bestaat niet; `process_video` nog niet gepland).

- [ ] **Step 3: Bewerk `app/main.py`**

Voeg `BackgroundTasks` toe aan de import:

```python
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
```

Vervang `_list_partial` door een versie die `any_processing` meegeeft:

```python
    def _list_partial(request: Request) -> HTMLResponse:
        sources = store.list_sources(project_id)
        questions = {s.id: store.list_questions(s.id) for s in sources}
        any_processing = any(s.processing for s in sources)
        return _TEMPLATES.TemplateResponse(
            request, "_source_list.html",
            {"sources": sources, "questions": questions, "any_processing": any_processing},
        )
```

Voeg `any_processing` ook toe aan de `index`-context:

```python
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        sources = store.list_sources(project_id)
        project = store.get_project(project_id)
        questions = {s.id: store.list_questions(s.id) for s in sources}
        any_processing = any(s.processing for s in sources)
        return _TEMPLATES.TemplateResponse(
            request, "index.html",
            {"sources": sources, "project": project, "questions": questions,
             "any_processing": any_processing},
        )
```

Voeg een poll-route toe (bijv. ná `index`):

```python
    @app.get("/sources", response_class=HTMLResponse)
    def sources_partial(request: Request):
        return _list_partial(request)
```

Vervang de hele `add_video`-route door de async-versie:

```python
    @app.post("/sources/video", response_class=HTMLResponse)
    def add_video(request: Request, background_tasks: BackgroundTasks, url: str = Form(...)):
        if urlparse(url).scheme not in ("http", "https"):
            raise HTTPException(status_code=400, detail="Alleen http(s)-URL's worden ondersteund.")
        src = Source(
            id=0, project_id=project_id, kind="video",
            title="Video wordt opgehaald…", position=0, included=True,
            text="", youtube_url=url, processing=True,
        )
        stored = store.add_source(project_id, src)
        background_tasks.add_task(process_video, store, settings, stored.id, url)
        return _list_partial(request)
```

- [ ] **Step 4: Run — verwacht PASS + volledige suite**

Run: `python3 -m pytest tests/test_routes.py -q`
Expected: PASS. Run dan `python3 -m pytest -q`. De helpers `_add_pdf_like_source` (transcript aanwezig) en `_add_transcriptless_video` (geen transcript) blijven werken: de achtergrondtaak draait in de TestClient ná het endpoint en gebruikt hun mocks (`video.fetch_raw`, `summarize`, en — waar getest — `extract_quote`), zodat de bron daarna gevuld is. Als een bestaande video-test faalt omdat hij op de directe respons assert i.p.v. de eindstaat, pas die test minimaal aan naar een `client.get("/")`/store-assert (zoals `test_add_video_lists_source` hierboven). Rapporteer welke je aanpaste.

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "$(printf 'feat: async add_video with background processing and poll route\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: UI — bezig-indicator + conditionele polling

**Files:**
- Modify: `app/templates/_source_list.html`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Consumes: `any_processing` + `s.processing` in de template-context (Task 3).
- Produces: de `<ul id="source-list">` pollt elke 2s (`hx-get="/sources"`) zolang `any_processing`; een bron met `processing` toont een "⏳ bezig met ophalen…"-rij (titel + verwijderknop), zonder de synopsis/vragen-UI.

- [ ] **Step 1: Schrijf de falende UI-test**

Voeg toe aan `tests/test_routes.py`:

```python
def test_processing_source_shows_indicator_and_polls(tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "process_video",
                        lambda store, settings, source_id, url: None)  # stays pending
    client = _client(tmp_path, monkeypatch)
    client.post("/sources/video", data={"url": "https://youtu.be/x"})
    body = client.get("/").text
    assert "bezig met ophalen" in body
    assert 'hx-get="/sources"' in body          # list polls while pending


def test_no_polling_when_nothing_processing(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    body = client.get("/").text
    assert 'hx-get="/sources"' not in body
```

- [ ] **Step 2: Run — verwacht FAIL**

Run: `python3 -m pytest tests/test_routes.py -k "indicator or polling" -v`
Expected: FAIL (geen `hx-get="/sources"` / "bezig met ophalen" in de markup).

- [ ] **Step 3: Bewerk `app/templates/_source_list.html`**

Maak de `<ul>`-openingstag conditioneel pollend en voeg een processing-tak toe in de loop. Vervang de bestaande `<ul id="source-list">`-opening en het begin van het `<li>` door:

```html
<ul id="source-list"{% if any_processing %} hx-get="/sources" hx-trigger="every 2s" hx-target="#source-list" hx-swap="outerHTML"{% endif %}>
  {% for s in sources %}
  <li data-id="{{ s.id }}">
    {% if s.processing %}
    <strong>{{ s.title }}</strong> <em>⏳ bezig met ophalen…</em>
    <form hx-post="/sources/{{ s.id }}/delete" hx-target="#source-list" hx-swap="outerHTML" style="display:inline">
      <button type="submit">verwijder</button>
    </form>
    {% else %}
```

Sluit de nieuwe `{% if %}` correct af: de bestaande inhoud van het `<li>` (de `<strong>{{ s.title }}</strong> … toggle/verwijder/video-details/vragen-UI …`) komt in de `{% else %}`-tak, en vóór de afsluitende `</li>` komt `{% endif %}`. Laat alle bestaande forms/`hx-*` in de else-tak ongewijzigd.

- [ ] **Step 4: Run — verwacht PASS + volledige suite**

Run: `python3 -m pytest -q`
Expected: PASS (alle tests, inclusief de 2 nieuwe UI-tests).

- [ ] **Step 5: Handmatige rooktest (aanbevolen)**

```bash
python3 -m uvicorn app.main:app --reload
# Plak een YouTube-URL -> de bron verschijnt DIRECT met "⏳ bezig met ophalen…";
# na ~15-130s verschijnt titel/thumbnail/synopsis/citaat vanzelf (lijst pollt elke 2s).
```

- [ ] **Step 6: Commit**

```bash
git add app/templates/_source_list.html tests/test_routes.py
git commit -m "$(printf 'feat: pending indicator and 2s polling for async video ingest\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Self-Review (uitgevoerd)

**Spec-dekking:**
- Direct toevoegen met "bezig"-status → Task 3 (`add_video` pending) + Task 1 (`processing`).
- Achtergrond fetch+synopsis+citaat → Task 2 (`process_video`) + Task 3 (BackgroundTask).
- Foutafhandeling "Ophalen mislukt" → Task 2 (`except` → `finish_video`).
- Live verversing (2s-polling tot klaar) → Task 4 (UI) + Task 3 (`GET /sources`, `any_processing`).

**Placeholder-scan:** geen TBD/TODO; elke code-stap bevat volledige code. De Task 4 template-stap beschrijft de `{% if %}/{% else %}/{% endif %}`-structuur expliciet rond de bestaande `<li>`-inhoud.

**Type-consistentie:** `Source.processing: bool` gelijk in model/store/render-context. `finish_video(...)` keyword-signatuur consistent tussen Task 1, de Task 2-aanroep en de tests. `process_video(store, settings, source_id, url)` consistent tussen Task 2 (def + unit-tests) en Task 3 (`background_tasks.add_task`). `any_processing` consistent tussen `_list_partial`/`index` (Task 3) en de template (Task 4).

**Bewust buiten scope (YAGNI):** echte taakwachtrij/SSE; retry-tuning (de retry blijft, maar staat nu off-request); voortgangspercentage.
