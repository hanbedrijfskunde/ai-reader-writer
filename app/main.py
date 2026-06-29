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
