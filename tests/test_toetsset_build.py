from app.models import ToetsVraag
from app.store import Store
from app.toets import build_toetsset


def _fake_generate(text, *, type, n, bloom_level):
    """Stand-in for the AI generator: returns n well-formed questions."""
    return [
        ToetsVraag(
            id=0, project_id=0, type=type, stem=f"{type} {i} [{bloom_level}]",
            answer="a", options=(["a", "b", "c", "d"] if type == "mc" else []),
        )
        for i in range(n)
    ]


def test_build_toetsset_distributes_by_weight_and_bloom(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    lo1 = store.add_learning_outcome(
        p.id, code="LU1", title="x", weight=0.5, bloom_level="Onthouden")  # all mc
    lo2 = store.add_learning_outcome(
        p.id, code="LU2", title="y", weight=0.5, bloom_level="Creëren")    # all open

    created = build_toetsset(store, p.id, total=10, reader_text="alle bronnen",
                             generate=_fake_generate)

    assert len(created) == 10
    saved = store.list_toetsvragen(p.id)
    assert len(saved) == 10
    lu1q = [q for q in saved if q.learning_outcome_id == lo1.id]
    lu2q = [q for q in saved if q.learning_outcome_id == lo2.id]
    assert len(lu1q) == 5 and all(q.type == "mc" for q in lu1q)     # Onthouden -> mc
    assert len(lu2q) == 5 and all(q.type == "open" for q in lu2q)   # Creëren -> open
    assert all(q.project_id == p.id for q in saved)


def test_build_toetsset_mixes_mc_and_open_for_mid_bloom(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    store.add_learning_outcome(
        p.id, code="LU", title="x", weight=1.0, bloom_level="Toepassen")  # 0.6 mc

    build_toetsset(store, p.id, total=10, reader_text="t", generate=_fake_generate)

    saved = store.list_toetsvragen(p.id)
    assert sum(1 for q in saved if q.type == "mc") == 6
    assert sum(1 for q in saved if q.type == "open") == 4


def test_build_toetsset_no_outcomes_generates_nothing(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    created = build_toetsset(store, p.id, total=10, reader_text="t",
                             generate=_fake_generate)
    assert created == []
