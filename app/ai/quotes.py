from __future__ import annotations

import re


def _default_caller(prompt: str, *, model: str, claude_key: str | None) -> str:
    from anthropic import Anthropic

    client = Anthropic(**{"api_key": claude_key})
    msg = client.messages.create(
        model=model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _is_verbatim(quote: str, text: str) -> bool:
    q = _normalize(quote)
    return bool(q) and q in _normalize(text)


def _clean(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
    # drop a single layer of surrounding straight or smart quotes
    if len(s) >= 2 and s[0] in "\"'"'" and s[-1] in "\"'"'":
        s = s[1:-1].strip()
    return s


def extract_quote(
    text: str,
    *,
    model: str,
    claude_key: str | None,
    _caller=None,
) -> str:
    if not text.strip():
        return ""
    prompt = (
        "Kies uit de onderstaande brontekst één korte, pakkende zin (max ~25 "
        "woorden) die de kern van de tekst raakt en geschikt is als motto boven "
        "een hoofdstuk. Kopieer de zin LETTERLIJK uit de tekst — verander geen "
        "woorden. Antwoord met UITSLUITEND die ene zin, zonder aanhalingstekens "
        "of toelichting.\n\nBrontekst:\n" + text[:8000]
    )
    caller = _caller or (lambda p: _default_caller(p, model=model, claude_key=claude_key))
    for _ in range(2):
        candidate = _clean(caller(prompt))
        if _is_verbatim(candidate, text):
            return candidate
    return ""
