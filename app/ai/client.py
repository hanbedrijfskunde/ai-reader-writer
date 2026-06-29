from __future__ import annotations


def _default_caller(prompt: str, *, model: str, claude_key: str | None) -> str:
    from anthropic import Anthropic

    client = Anthropic(claude_key)
    msg = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")


def summarize(
    transcript: str,
    *,
    model: str,
    claude_key: str | None,
    max_words: int = 120,
    _caller=None,
) -> str:
    prompt = (
        "Vat het volgende videotranscript samen in een heldere Nederlandse "
        f"synopsis van maximaal {max_words} woorden voor HBO-studenten. "
        "Geef alleen de synopsis, geen inleiding.\n\n"
        f"Transcript:\n{transcript}"
    )
    caller = _caller or (lambda p: _default_caller(p, model=model, claude_key=claude_key))
    return caller(prompt).strip()
