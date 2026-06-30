from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.models import LearningOutcome, Project, Question, Source, ToetsVraag

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
    synopsis TEXT,
    quote TEXT,
    processing INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learning_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    weight REAL NOT NULL DEFAULT 0,
    position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS toetsvragen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    learning_outcome_id INTEGER REFERENCES learning_outcomes(id) ON DELETE SET NULL,
    source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    type TEXT NOT NULL,
    bloom_level TEXT,
    stem TEXT NOT NULL,
    options TEXT NOT NULL DEFAULT '[]',
    answer TEXT NOT NULL DEFAULT '',
    validity INTEGER,
    reliability INTEGER,
    technical INTEGER,
    notes TEXT,
    position INTEGER NOT NULL DEFAULT 0
);
"""

_SOURCE_COLS = [
    "id", "project_id", "kind", "title", "position", "included", "text",
    "filename", "page_count", "youtube_url", "video_id", "channel",
    "duration", "thumbnail_url", "synopsis", "quote", "processing",
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
        self._ensure_source_columns()
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

    _SOURCE_META_COLS = {"quote": "TEXT", "processing": "INTEGER NOT NULL DEFAULT 0"}

    def _ensure_source_columns(self) -> None:
        existing = {r["name"] for r in self._conn.execute("PRAGMA table_info(sources)")}
        for col, col_type in self._SOURCE_META_COLS.items():
            if col not in existing:
                self._conn.execute(f"ALTER TABLE sources ADD COLUMN {col} {col_type}")
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
        data["processing"] = bool(data["processing"])
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
                thumbnail_url, synopsis, quote, processing)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (project_id, source.kind, source.title, next_pos,
             int(source.included), source.text, source.filename,
             source.page_count, source.youtube_url, source.video_id,
             source.channel, source.duration, source.thumbnail_url,
             source.synopsis, source.quote, int(source.processing)),
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

    def set_synopsis(self, source_id: int, synopsis: str | None) -> None:
        self._conn.execute(
            "UPDATE sources SET synopsis = ? WHERE id = ?", (synopsis, source_id)
        )
        self._conn.commit()

    def set_source_text(self, source_id: int, text: str) -> None:
        self._conn.execute(
            "UPDATE sources SET text = ? WHERE id = ?", (text, source_id)
        )
        self._conn.commit()

    def set_quote(self, source_id: int, quote: str | None) -> None:
        self._conn.execute(
            "UPDATE sources SET quote = ? WHERE id = ?", (quote, source_id)
        )
        self._conn.commit()

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

    def _row_to_outcome(self, row: sqlite3.Row) -> LearningOutcome:
        return LearningOutcome(
            id=row["id"], project_id=row["project_id"], code=row["code"],
            title=row["title"], weight=row["weight"], position=row["position"],
        )

    def add_learning_outcome(
        self, project_id: int, *, code: str, title: str, weight: float
    ) -> LearningOutcome:
        next_pos = self._conn.execute(
            "SELECT COALESCE(MAX(position) + 1, 0) AS p FROM learning_outcomes "
            "WHERE project_id = ?",
            (project_id,),
        ).fetchone()["p"]
        cur = self._conn.execute(
            "INSERT INTO learning_outcomes (project_id, code, title, weight, position) "
            "VALUES (?,?,?,?,?)",
            (project_id, code, title, weight, next_pos),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM learning_outcomes WHERE id = ?", (int(cur.lastrowid),)
        ).fetchone()
        return self._row_to_outcome(row)

    def list_learning_outcomes(self, project_id: int) -> list[LearningOutcome]:
        rows = self._conn.execute(
            "SELECT * FROM learning_outcomes WHERE project_id = ? ORDER BY position",
            (project_id,),
        ).fetchall()
        return [self._row_to_outcome(r) for r in rows]

    def update_learning_outcome(
        self, outcome_id: int, *, code: str, title: str, weight: float
    ) -> None:
        self._conn.execute(
            "UPDATE learning_outcomes SET code = ?, title = ?, weight = ? WHERE id = ?",
            (code, title, weight, outcome_id),
        )
        self._conn.commit()

    def delete_learning_outcome(self, outcome_id: int) -> None:
        self._conn.execute(
            "DELETE FROM learning_outcomes WHERE id = ?", (outcome_id,)
        )
        self._conn.commit()

    def _row_to_toetsvraag(self, row: sqlite3.Row) -> ToetsVraag:
        return ToetsVraag(
            id=row["id"], project_id=row["project_id"],
            learning_outcome_id=row["learning_outcome_id"], source_id=row["source_id"],
            type=row["type"], bloom_level=row["bloom_level"], stem=row["stem"],
            options=json.loads(row["options"]), answer=row["answer"],
            validity=row["validity"], reliability=row["reliability"],
            technical=row["technical"], notes=row["notes"], position=row["position"],
        )

    def add_toetsvraag(self, project_id: int, vraag: ToetsVraag) -> ToetsVraag:
        next_pos = self._conn.execute(
            "SELECT COALESCE(MAX(position) + 1, 0) AS p FROM toetsvragen "
            "WHERE project_id = ?",
            (project_id,),
        ).fetchone()["p"]
        cur = self._conn.execute(
            "INSERT INTO toetsvragen (project_id, learning_outcome_id, source_id, "
            "type, bloom_level, stem, options, answer, validity, reliability, "
            "technical, notes, position) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (project_id, vraag.learning_outcome_id, vraag.source_id, vraag.type,
             vraag.bloom_level, vraag.stem, json.dumps(vraag.options), vraag.answer,
             vraag.validity, vraag.reliability, vraag.technical, vraag.notes, next_pos),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM toetsvragen WHERE id = ?", (int(cur.lastrowid),)
        ).fetchone()
        return self._row_to_toetsvraag(row)

    def list_toetsvragen(self, project_id: int) -> list[ToetsVraag]:
        rows = self._conn.execute(
            "SELECT * FROM toetsvragen WHERE project_id = ? ORDER BY position",
            (project_id,),
        ).fetchall()
        return [self._row_to_toetsvraag(r) for r in rows]

    def set_toetsvraag_scores(
        self, vraag_id: int, *, validity: int | None, reliability: int | None,
        technical: int | None, notes: str | None = None,
    ) -> None:
        self._conn.execute(
            "UPDATE toetsvragen SET validity = ?, reliability = ?, technical = ?, "
            "notes = ? WHERE id = ?",
            (validity, reliability, technical, notes, vraag_id),
        )
        self._conn.commit()

    def delete_toetsvraag(self, vraag_id: int) -> None:
        self._conn.execute("DELETE FROM toetsvragen WHERE id = ?", (vraag_id,))
        self._conn.commit()
