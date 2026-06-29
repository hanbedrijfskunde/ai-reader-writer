from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import load_settings
from app.ingest import pdf, video
from app.ai.client import summarize  # noqa: F401  (monkeypatch-doel in tests)
from app.ai.questions import generate_questions  # noqa: F401  (monkeypatch-doel in tests)
from app.ai.quotes import extract_quote  # noqa: F401  (monkeypatch-doel in tests)
from app.models import Source
from app.render import html as render_html
from app.render.pdf import html_to_pdf  # noqa: F401  (monkeypatch-doel in tests)
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
        questions = {s.id: store.list_questions(s.id) for s in sources}
        return _TEMPLATES.TemplateResponse(
            request, "_source_list.html",
            {"sources": sources, "questions": questions},
        )

    def _autoquote(stored: Source) -> None:
        if stored.text.strip():
            quote = extract_quote(
                stored.text, model=settings.default_model,
                claude_key=settings.anthropic_key,
            )
            if quote:
                store.set_quote(stored.id, quote)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        sources = store.list_sources(project_id)
        project = store.get_project(project_id)
        questions = {s.id: store.list_questions(s.id) for s in sources}
        return _TEMPLATES.TemplateResponse(
            request, "index.html",
            {"sources": sources, "project": project, "questions": questions},
        )

    @app.post("/meta", response_class=HTMLResponse)
    def save_meta(
        reader_title: str = Form(""),
        module_code: str = Form(""),
        academic_year: str = Form(""),
    ):
        store.set_meta(
            project_id,
            reader_title.strip() or None,
            module_code.strip() or None,
            academic_year.strip() or None,
        )
        return HTMLResponse("<span>Opgeslagen ✓</span>")

    @app.post("/sources/pdf", response_class=HTMLResponse)
    async def add_pdf(request: Request, file: UploadFile = File(...)):
        sanitized_filename = Path(file.filename).name
        dest = settings.upload_dir / sanitized_filename
        dest.write_bytes(await file.read())
        src = Source(
            id=0, project_id=project_id, kind="document",
            title=Path(sanitized_filename).stem, position=0, included=True,
            text=pdf.extract_text(dest), filename=sanitized_filename,
            page_count=pdf.page_count(dest),
        )
        stored = store.add_source(project_id, src)
        _autoquote(stored)
        return _list_partial(request)

    @app.post("/sources/video", response_class=HTMLResponse)
    def add_video(request: Request, url: str = Form(...)):
        if urlparse(url).scheme not in ("http", "https"):
            raise HTTPException(status_code=400, detail="Alleen http(s)-URL's worden ondersteund.")
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
        stored = store.add_source(project_id, src)
        _autoquote(stored)
        return _list_partial(request)

    @app.post("/sources/reorder", response_class=HTMLResponse)
    def reorder(request: Request, ordered_ids: str = Form(...)):
        ids = [int(x) for x in ordered_ids.split(",") if x.strip()]
        store.reorder_sources(project_id, ids)
        return _list_partial(request)

    @app.post("/sources/{source_id}/content", response_class=HTMLResponse)
    def edit_content(
        request: Request,
        source_id: int,
        transcript: str = Form(""),
        synopsis: str = Form(""),
    ):
        transcript = transcript.strip()
        synopsis = synopsis.strip()
        # Pasting a transcript stores it and (unless the teacher also typed a
        # synopsis) lets the AI generate one — the manual escape hatch for
        # videos whose transcript YouTube withholds from automated fetching.
        if transcript:
            store.set_source_text(source_id, transcript)
            if not synopsis:
                synopsis = summarize(
                    transcript, model=settings.default_model,
                    claude_key=settings.anthropic_key,
                )
        if synopsis:
            store.set_synopsis(source_id, synopsis)
        return _list_partial(request)

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
        if text.strip():
            store.update_question(question_id, text.strip())
        return _list_partial(request)

    @app.post("/questions/{question_id}/delete", response_class=HTMLResponse)
    def delete_q(request: Request, question_id: int):
        store.delete_question(question_id)
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

    def _build_reader_html() -> Path:
        sources = store.list_sources(project_id)
        project = store.get_project(project_id)
        title = project.reader_title or project.name
        meta_parts = [p for p in (project.module_code, project.academic_year) if p]
        subtitle = " · ".join(meta_parts) if meta_parts else None
        questions_by_source = {
            s.id: [q.text for q in store.list_questions(s.id)] for s in sources
        }
        quotes_by_source = {
            s.id: s.quote for s in sources if s.quote
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
            quotes_by_source=quotes_by_source,
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

    return app


app = create_app()
