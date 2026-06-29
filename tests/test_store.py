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


def test_set_and_get_meta(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    store.set_meta(p.id, reader_title="Strategie 1", module_code="BK-101",
                   academic_year="2025-2026")
    got = store.get_project(p.id)
    assert got.reader_title == "Strategie 1"
    assert got.module_code == "BK-101"
    assert got.academic_year == "2025-2026"


def test_meta_migration_on_legacy_db(tmp_path):
    import sqlite3
    db = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'concept', bloom_level TEXT)"
    )
    conn.execute("INSERT INTO projects (name) VALUES ('Oud')")
    conn.commit()
    conn.close()
    store = Store(db)  # opening must migrate the legacy table
    store.set_meta(1, reader_title="T", module_code="C", academic_year="Y")
    got = store.get_project(1)
    assert (got.reader_title, got.module_code, got.academic_year) == ("T", "C", "Y")


def test_set_synopsis_and_source_text(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    s = store.add_source(p.id, Source(
        id=0, project_id=0, kind="video", title="V", position=0,
        included=True, text="", synopsis=None, youtube_url="https://y/x",
    ))
    store.set_synopsis(s.id, "Handmatige synopsis")
    store.set_source_text(s.id, "het transcript")
    got = store.list_sources(p.id)[0]
    assert got.synopsis == "Handmatige synopsis"
    assert got.text == "het transcript"


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
