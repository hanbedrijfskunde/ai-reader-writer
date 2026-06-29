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
