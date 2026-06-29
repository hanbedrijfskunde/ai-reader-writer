import pytest
from app.ai import questions


def test_generate_questions_parses_json_array():
    raw = '["Waarom werkt dit?", "Hoe pas je dit toe?", "Wat is een risico?"]'
    qs = questions.generate_questions(
        "brontekst", "Toepassen", n=3, model="claude-sonnet-4-6",
        claude_key=None, _caller=lambda p: raw,
    )
    assert qs == ["Waarom werkt dit?", "Hoe pas je dit toe?", "Wat is een risico?"]


def test_generate_questions_strips_code_fence_and_caps_n():
    raw = '```json\n["a", "b", "c", "d"]\n```'
    qs = questions.generate_questions(
        "t", "Begrijpen", n=2, model="m", claude_key=None, _caller=lambda p: raw,
    )
    assert qs == ["a", "b"]


def test_generate_questions_retries_then_raises_on_bad_output():
    calls = {"n": 0}

    def bad(_p):
        calls["n"] += 1
        return "dit is geen json"

    with pytest.raises(ValueError):
        questions.generate_questions(
            "t", "Onthouden", n=3, model="m", claude_key=None, _caller=bad,
        )
    assert calls["n"] == 2  # één retry


def test_generate_questions_prompt_includes_bloom_level():
    seen = {}

    def cap(prompt):
        seen["p"] = prompt
        return '["x"]'

    questions.generate_questions("t", "Analyseren", n=1, model="m",
                                 claude_key=None, _caller=cap)
    assert "Analyseren" in seen["p"]


def test_generate_questions_rejects_empty_array():
    calls = {"n": 0}

    def empty(_p):
        calls["n"] += 1
        return "[]"

    with pytest.raises(ValueError):
        questions.generate_questions(
            "t", "Begrijpen", n=3, model="m", claude_key=None, _caller=empty,
        )
    assert calls["n"] == 2
