import json

from app.ai.toetsvragen import generate_toets_questions


def _mc_payload(items):
    return json.dumps(items)


def test_generates_mc_questions_from_caller():
    payload = _mc_payload([
        {"stam": "Wat is een TOM?",
         "opties": ["Een organogram", "Een operating model", "Een KPI", "Een audit"],
         "sleutel": "Een operating model"},
        {"stam": "Welke laag hoort bij een TOM?",
         "opties": ["Marketing", "Processen", "Notulen", "Parkeren"],
         "sleutel": "Processen"},
    ])
    qs = generate_toets_questions(
        "brontekst", type="mc", n=2, bloom_level="Begrijpen",
        model="m", claude_key=None, _caller=lambda p: payload,
    )
    assert len(qs) == 2
    assert qs[0].type == "mc"
    assert qs[0].stem == "Wat is een TOM?"
    assert qs[0].options == ["Een organogram", "Een operating model", "Een KPI", "Een audit"]
    assert qs[0].answer == "Een operating model"
    assert qs[0].bloom_level == "Begrijpen"


def test_generates_open_questions():
    payload = json.dumps([{"stam": "Leg uit waarom een TOM nodig is.",
                           "modelantwoord": "Omdat strategie anders intentie blijft."}])
    qs = generate_toets_questions(
        "brontekst", type="open", n=1, bloom_level="Analyseren",
        model="m", claude_key=None, _caller=lambda p: payload,
    )
    assert qs[0].type == "open"
    assert qs[0].options == []
    assert qs[0].answer == "Omdat strategie anders intentie blijft."
    assert qs[0].stem == "Leg uit waarom een TOM nodig is."


def test_mc_answer_must_be_one_of_options_else_retry():
    bad = json.dumps([{"stam": "x", "opties": ["a", "b", "c", "d"], "sleutel": "z"}])
    good = json.dumps([{"stam": "x", "opties": ["a", "b", "c", "d"], "sleutel": "b"}])
    calls = [bad, good]
    qs = generate_toets_questions(
        "brontekst", type="mc", n=1, bloom_level="Begrijpen",
        model="m", claude_key=None, _caller=lambda p: calls.pop(0),
    )
    assert qs[0].answer == "b"


def test_prompt_includes_bloom_count_type_and_source():
    seen = {}

    def cap(p):
        seen["p"] = p
        return json.dumps([{"stam": "x", "opties": ["a", "b", "c", "d"], "sleutel": "a"}])

    generate_toets_questions(
        "BRONINHOUD", type="mc", n=3, bloom_level="Toepassen",
        model="m", claude_key=None, _caller=cap,
    )
    assert "Toepassen" in seen["p"]
    assert "BRONINHOUD" in seen["p"]
    assert "3" in seen["p"]


def test_strips_code_fence():
    payload = "```json\n" + json.dumps(
        [{"stam": "x", "opties": ["a", "b", "c", "d"], "sleutel": "a"}]) + "\n```"
    qs = generate_toets_questions(
        "brontekst", type="mc", n=1, bloom_level="Begrijpen",
        model="m", claude_key=None, _caller=lambda p: payload,
    )
    assert qs[0].stem == "x"
