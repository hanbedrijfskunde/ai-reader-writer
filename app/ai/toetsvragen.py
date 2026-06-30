from __future__ import annotations

import json

from app.models import ToetsVraag

# Beknopte handboekregels (workflow-toets-samenstelling.html §2) als
# generatie-instructie — niet dupliceren, alleen de kern als sturing.
_MC_RULES = (
    "Constructie-eisen voor meerkeuzevragen (handboek toetssamenstelling):\n"
    "- Eén duidelijk juiste sleutel; precies vier opties (A–D).\n"
    "- Plausibele afleiders, óók bij lagere Bloom-niveaus; geen onzin-opties.\n"
    "- Toets kernconcepten, geen triviale details.\n"
    "- Vermijd 'alle bovenstaande', dubbele ontkenning en lengte-bias "
    "(maak de sleutel niet stelselmatig de langste optie).\n"
    "- Geen onderwerpdubbeling tussen vragen in deze batch.\n"
)
_OPEN_RULES = (
    "Constructie-eisen voor open vragen (handboek toetssamenstelling):\n"
    "- Eén heldere opdracht die het beoogde cognitieve niveau uitlokt.\n"
    "- Lever een bondig modelantwoord dat als beoordelingswijzer dient.\n"
    "- Toets kernconcepten en redeneren, geen losse feitreproductie.\n"
)


def _default_caller(prompt: str, *, model: str, claude_key: str | None) -> str:
    from anthropic import Anthropic

    client = Anthropic(**{"api_key": claude_key})
    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")


def _strip_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _parse_mc(data: list, bloom_level: str) -> list[ToetsVraag]:
    out: list[ToetsVraag] = []
    for item in data:
        stem = str(item["stam"]).strip()
        options = [str(o).strip() for o in item["opties"]]
        answer = str(item["sleutel"]).strip()
        if not stem or len(options) < 2 or answer not in options:
            raise ValueError("ongeldige mc-vraag: sleutel moet één van de opties zijn")
        out.append(ToetsVraag(
            id=0, project_id=0, type="mc", stem=stem,
            bloom_level=bloom_level, options=options, answer=answer,
        ))
    return out


def _parse_open(data: list, bloom_level: str) -> list[ToetsVraag]:
    out: list[ToetsVraag] = []
    for item in data:
        stem = str(item["stam"]).strip()
        answer = str(item["modelantwoord"]).strip()
        if not stem or not answer:
            raise ValueError("ongeldige open vraag: stam en modelantwoord vereist")
        out.append(ToetsVraag(
            id=0, project_id=0, type="open", stem=stem,
            bloom_level=bloom_level, options=[], answer=answer,
        ))
    return out


def generate_toets_questions(
    text: str,
    *,
    type: str,
    n: int,
    bloom_level: str,
    model: str,
    claude_key: str | None,
    _caller=None,
) -> list[ToetsVraag]:
    """Genereer `n` toetsvragen van een type ("mc" | "open") op een Bloom-niveau
    uit de brontekst, volgens de handboekregels. Retourneert (nog niet
    opgeslagen) ToetsVraag-objecten; beoordeling/scores volgen in een aparte
    stap. Vraagt het model om strikte JSON en valideert/herhaalt bij onzin.
    """
    if type == "mc":
        rules, shape = _MC_RULES, (
            'JSON-array van objecten {"stam": str, "opties": [vier strings], '
            '"sleutel": de exacte tekst van de juiste optie}'
        )
    elif type == "open":
        rules, shape = _OPEN_RULES, (
            'JSON-array van objecten {"stam": str, "modelantwoord": str}'
        )
    else:
        raise ValueError(f"onbekend vraagtype: {type!r}")

    prompt = (
        f"Genereer {n} {'meerkeuzevragen' if type == 'mc' else 'open vragen'} in het "
        f"Nederlands voor HBO-studenten op Bloom-niveau '{bloom_level}'. De vragen "
        "gaan over de onderstaande brontekst.\n\n"
        f"{rules}\n"
        f"Antwoord met UITSLUITEND een {shape}, niets anders.\n\n"
        f"Brontekst:\n{text[:8000]}"
    )
    caller = _caller or (lambda p: _default_caller(p, model=model, claude_key=claude_key))
    parse = _parse_mc if type == "mc" else _parse_open
    last_err: Exception | None = None
    for _ in range(2):
        raw = caller(prompt)
        try:
            data = json.loads(_strip_fence(raw))
            if not isinstance(data, list) or not data:
                raise ValueError("verwacht een niet-lege JSON-array")
            return parse(data, bloom_level)[:n]
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            last_err = e
    raise ValueError(f"kon geen geldige toetsvragen genereren: {last_err}")
