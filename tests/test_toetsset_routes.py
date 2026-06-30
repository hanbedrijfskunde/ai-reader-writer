from fastapi.testclient import TestClient

from app.models import Source, ToetsVraag


def _client(tmp_path, monkeypatch):
    from app.config import load_settings
    import app.main as main
    settings = load_settings(env_file=tmp_path / "none.env", data_dir=tmp_path / "data")
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    return TestClient(main.create_app())


def _store(client):
    return client.app.state.store


def _pid(client):
    return client.app.state.project_id


def test_add_learning_outcome_route(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/outcomes", data={
        "code": "LU1", "title": "Begrijpt het TOM", "weight": "0.6",
        "bloom_level": "Begrijpen"})
    assert resp.status_code == 200
    los = _store(client).list_learning_outcomes(_pid(client))
    assert len(los) == 1
    assert los[0].code == "LU1" and los[0].weight == 0.6
    assert los[0].bloom_level == "Begrijpen"
    assert "LU1" in resp.text


def test_delete_learning_outcome_route(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/outcomes", data={"code": "LU1", "title": "x", "weight": "1",
                                    "bloom_level": "Begrijpen"})
    lo = _store(client).list_learning_outcomes(_pid(client))[0]
    resp = client.post(f"/outcomes/{lo.id}/delete")
    assert resp.status_code == 200
    assert _store(client).list_learning_outcomes(_pid(client)) == []


def test_set_status_definitief_route(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/status", data={"status": "Definitief"})
    assert resp.status_code == 200
    assert _store(client).get_project(_pid(client)).status == "Definitief"


def test_generate_toetsset_blocked_until_definitief(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    client.post("/outcomes", data={"code": "LU1", "title": "x", "weight": "1",
                                    "bloom_level": "Onthouden"})
    called = {"n": 0}

    def fake_gen(text, **kw):
        called["n"] += 1
        return []

    monkeypatch.setattr(main, "generate_toets_questions", fake_gen)
    resp = client.post("/toetsset/generate", data={"total": "10"})  # still 'concept'
    assert resp.status_code == 200
    assert called["n"] == 0
    assert _store(client).list_toetsvragen(_pid(client)) == []


def test_generate_toetsset_when_definitief(tmp_path, monkeypatch):
    import app.main as main
    client = _client(tmp_path, monkeypatch)
    st, pid = _store(client), _pid(client)
    st.add_source(pid, Source(id=0, project_id=pid, kind="document", title="d",
                              position=0, included=True, text="inhoud over TOM"))
    client.post("/outcomes", data={"code": "LU1", "title": "x", "weight": "1",
                                    "bloom_level": "Onthouden"})
    client.post("/status", data={"status": "Definitief"})

    def fake_gen(text, *, type, n, bloom_level, **kw):
        return [ToetsVraag(id=0, project_id=0, type=type, stem=f"{type}{i}",
                           answer="a", options=(["a", "b", "c", "d"] if type == "mc" else []))
                for i in range(n)]

    monkeypatch.setattr(main, "generate_toets_questions", fake_gen)
    resp = client.post("/toetsset/generate", data={"total": "10"})
    assert resp.status_code == 200
    assert len(st.list_toetsvragen(pid)) == 10


def test_export_toetsset_csv_route(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    st, pid = _store(client), _pid(client)
    lo = st.add_learning_outcome(pid, code="LU1", title="x", weight=1.0,
                                 bloom_level="Begrijpen")
    st.add_toetsvraag(pid, ToetsVraag(
        id=0, project_id=pid, type="mc", stem="Wat is een TOM?",
        learning_outcome_id=lo.id, options=["a", "b", "c", "d"], answer="a"))
    resp = client.get("/toetsset/export/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    cd = resp.headers["content-disposition"]
    assert "attachment" in cd and "toetsset.csv" in cd
    assert "leeruitkomst" in resp.text       # header row
    assert "Wat is een TOM?" in resp.text
    assert "LU1" in resp.text


def test_index_shows_csv_export_link_when_questions_exist(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    st, pid = _store(client), _pid(client)
    st.add_toetsvraag(pid, ToetsVraag(id=0, project_id=pid, type="open",
                                      stem="Leg uit.", answer="y"))
    body = client.get("/").text
    assert "/toetsset/export/csv" in body


def test_index_shows_toetsset_section(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    body = client.get("/").text
    assert "Leeruitkomsten" in body
    assert 'hx-post="/outcomes"' in body
    assert 'hx-post="/toetsset/generate"' in body or 'hx-post="/status"' in body
