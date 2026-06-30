from app.models import ToetsVraag
from app.store import Store


def _mc(project_id, lo_id):
    return ToetsVraag(
        id=0, project_id=project_id, type="mc", stem="Wat is een TOM?",
        learning_outcome_id=lo_id, bloom_level="Begrijpen",
        options=["A", "B", "C", "D"], answer="A",
    )


def test_add_and_list_toetsvragen_roundtrips_options(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    lo = store.add_learning_outcome(p.id, code="LU1", title="x", weight=1.0)
    stored = store.add_toetsvraag(p.id, _mc(p.id, lo.id))

    assert stored.id > 0
    got = store.list_toetsvragen(p.id)
    assert len(got) == 1
    assert got[0].type == "mc"
    assert got[0].stem == "Wat is een TOM?"
    assert got[0].options == ["A", "B", "C", "D"]   # round-trips through JSON
    assert got[0].answer == "A"
    assert got[0].learning_outcome_id == lo.id
    assert got[0].bloom_level == "Begrijpen"


def test_open_question_has_no_options(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    v = ToetsVraag(id=0, project_id=p.id, type="open",
                   stem="Leg uit waarom een TOM nodig is.", answer="Modelantwoord.")
    store.add_toetsvraag(p.id, v)
    got = store.list_toetsvragen(p.id)[0]
    assert got.type == "open"
    assert got.options == []
    assert got.answer == "Modelantwoord."


def test_set_toetsvraag_scores(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    v = store.add_toetsvraag(p.id, _mc(p.id, None))
    assert (v.validity, v.reliability, v.technical) == (None, None, None)
    store.set_toetsvraag_scores(v.id, validity=4, reliability=5, technical=4, notes="ok")
    got = store.list_toetsvragen(p.id)[0]
    assert (got.validity, got.reliability, got.technical) == (4, 5, 4)
    assert got.notes == "ok"


def test_delete_toetsvraag(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    v = store.add_toetsvraag(p.id, _mc(p.id, None))
    store.delete_toetsvraag(v.id)
    assert store.list_toetsvragen(p.id) == []
