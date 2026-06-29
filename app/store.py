from __future__ import annotations

import sqlite3
from pathlib import Path

from app.models import Project, Source

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'concept',
    bloom_level TEXT,
    reader_title TEXT,
    module_code TEXT,
    academic_year TEXT
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
        # check_same_thread=False: FastAPI runs sync handlers in a threadpool; for
        # this single-user local app the risk of concurrent writes is negligible.
        # A multi-user deployment would need per-request connections or a lock.
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._ensure_project_columns()
        self._conn.commit()

    # Columns added after the first release; ALTER them onto pre-existing DBs.
    _PROJECT_META_COLS = {
        "reader_title": "TEXT",
        "module_code": "TEXT",
        "academic_year": "TEXT",
    }

    def _ensure_project_columns(self) -> None:
        existing = {r["name"] for r in self._conn.execute("PRAGMA table_info(projects)")}
        for col, col_type in self._PROJECT_META_COLS.items():
            if col not in existing:
                self._conn.execute(f"ALTER TABLE projects ADD COLUMN {col} {col_type}")
        self._conn.commit()

    def create_project(self, name: str) -> Project:
        cur = self._conn.execute("INSERT INTO projects (name) VALUES (?)", (name,))
        self._conn.commit()
        return self.get_project(int(cur.lastrowid))

    def get_project(self, project_id: int) -> Project:
        row = self._conn.execute(
            "SELECT id, name, status, bloom_level, reader_title, module_code, "
            "academic_year FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"project {project_id} not found")
        return Project(id=row["id"], name=row["name"], status=row["status"],
                       bloom_level=row["bloom_level"], reader_title=row["reader_title"],
                       module_code=row["module_code"], academic_year=row["academic_year"])

    def set_status(self, project_id: int, status: str) -> None:
        self._conn.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
        self._conn.commit()

    def set_meta(
        self,
        project_id: int,
        reader_title: str | None,
        module_code: str | None,
        academic_year: str | None,
    ) -> None:
        self._conn.execute(
            "UPDATE projects SET reader_title = ?, module_code = ?, academic_year = ? "
            "WHERE id = ?",
            (reader_title, module_code, academic_year, project_id),
        )
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
