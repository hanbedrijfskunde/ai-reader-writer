from app.ai import quotes

SOURCE = (
    "Leiderschap is geen positie maar gedrag.\n"
    "Een goede leider schept duidelijkheid en vertrouwen in het team."
)


def test_is_verbatim_normalizes_whitespace():
    assert quotes._is_verbatim("Leiderschap is geen   positie maar gedrag.", SOURCE)
    assert quotes._is_verbatim("schept duidelijkheid en vertrouwen", SOURCE)
    assert not quotes._is_verbatim("dit staat er niet", SOURCE)


def test_extract_quote_returns_verbatim_substring():
    q = quotes.extract_quote(
        SOURCE, model="m", claude_key=None,
        _caller=lambda p: "Leiderschap is geen positie maar gedrag.",
    )
    assert q == "Leiderschap is geen positie maar gedrag."


def test_extract_quote_strips_surrounding_quotes_and_fences():
    q = quotes.extract_quote(
        SOURCE, model="m", claude_key=None,
        _caller=lambda p: '"schept duidelijkheid en vertrouwen in het team."',
    )
    assert q == "schept duidelijkheid en vertrouwen in het team."


def test_extract_quote_retries_then_empty_when_not_verbatim():
    calls = {"n": 0}

    def hallucinate(_p):
        calls["n"] += 1
        return "Een verzonnen zin die niet in de bron staat."

    q = quotes.extract_quote(SOURCE, model="m", claude_key=None, _caller=hallucinate)
    assert q == ""
    assert calls["n"] == 2  # one retry before giving up


def test_extract_quote_empty_text_returns_empty():
    assert quotes.extract_quote("", model="m", claude_key=None, _caller=lambda p: "x") == ""
