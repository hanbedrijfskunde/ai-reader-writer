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
