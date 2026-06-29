from __future__ import annotations

import json

_BLOOM_VERBS = {
    "Onthouden": "benoemen, opsommen, definiëren",
    "Begrijpen": "uitleggen, samenvatten, vergelijken",
    "Toepassen": "toepassen, demonstreren, gebruiken",
    "Analyseren": "analyseren, onderscheiden, relateren",
    "Evalueren": "beoordelen, bekritiseren, verdedigen",
    "Creëren": "ontwerpen, ontwikkelen, formuleren",
}


def _default_caller(prompt: str, *, model: str, claude_key: str | None) -> str:
    from anthropic import Anthropic

    client = Anthropic(**{"api_key": claude_key})
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")


def _parse_questions(raw: str) -> list[str]:
    s = raw.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        # drop the opening ```lang line and a trailing ``` line if present
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    data = json.loads(s)
    if not isinstance(data, list) or not data or not all(
        isinstance(x, str) and x.strip() for x in data
    ):
        raise ValueError("verwacht een niet-lege JSON-array van vraag-strings")
    return [x.strip() for x in data]


def generate_questions(
    text: str,
    bloom_level: str,
    n: int = 3,
    *,
    model: str,
    claude_key: str | None,
    _caller=None,
) -> list[str]:
    verbs = _BLOOM_VERBS.get(bloom_level, "")
    prompt = (
        f"Genereer {n} open verdiepende reflectievragen in het Nederlands voor "
        f"HBO-studenten op Bloom-niveau '{bloom_level}' "
        f"(passende werkwoorden: {verbs}). De vragen gaan over de onderstaande "
        "brontekst en zetten aan tot nadenken/toepassen — geen feitvragen met "
        "één goed antwoord, en geef GEEN antwoorden. "
        "Antwoord met UITSLUITEND een JSON-array van vraag-strings, niets anders.\n\n"
        f"Brontekst:\n{text[:8000]}"
    )
    caller = _caller or (lambda p: _default_caller(p, model=model, claude_key=claude_key))
    last_err: Exception | None = None
    for _ in range(2):
        raw = caller(prompt)
        try:
            return _parse_questions(raw)[:n]
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
    raise ValueError(f"kon geen geldige vragen genereren: {last_err}")
