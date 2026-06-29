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
