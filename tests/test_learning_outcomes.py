from app.store import Store


def test_add_and_list_learning_outcomes(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    lo1 = store.add_learning_outcome(p.id, code="LU1", title="Begrijpt het TOM", weight=0.6)
    lo2 = store.add_learning_outcome(p.id, code="LU2", title="Past strategy maps toe", weight=0.4)

    assert lo1.id != lo2.id
    los = store.list_learning_outcomes(p.id)
    assert [lo.code for lo in los] == ["LU1", "LU2"]   # ordered by position
    assert los[0].title == "Begrijpt het TOM"
    assert los[0].weight == 0.6 and los[1].weight == 0.4


def test_update_learning_outcome(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    lo = store.add_learning_outcome(p.id, code="LU1", title="Oud", weight=0.5)
    store.update_learning_outcome(lo.id, code="LU1", title="Nieuw", weight=0.75)
    got = store.list_learning_outcomes(p.id)[0]
    assert got.title == "Nieuw" and got.weight == 0.75


def test_delete_learning_outcome(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    p = store.create_project("M")
    lo = store.add_learning_outcome(p.id, code="LU1", title="Weg", weight=1.0)
    store.delete_learning_outcome(lo.id)
    assert store.list_learning_outcomes(p.id) == []
