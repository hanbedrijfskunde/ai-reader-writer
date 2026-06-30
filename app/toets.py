from __future__ import annotations

import math

# Aandeel meerkeuze per Bloom-niveau (handboek §10): lagere niveaus lenen zich
# voor mc, hogere voor open. De rest van het aantal wordt open. Onbekend/None
# valt terug op een gebalanceerde mix.
_MC_FRACTION = {
    "Onthouden": 1.0,
    "Begrijpen": 0.8,
    "Toepassen": 0.6,
    "Analyseren": 0.4,
    "Evalueren": 0.2,
    "Creëren": 0.0,
}
_DEFAULT_MC_FRACTION = 0.6


def distribute_questions(total: int, weights: list[float]) -> list[int]:
    """Verdeel `total` toetsvragen over leeruitkomsten naar rato van hun wegingen.

    Gebruikt de largest-remainder (Hamilton) methode: floor elk evenredig
    deel en ken de resterende eenheden toe aan de grootste resten. Zo tellen
    de deelaantallen exact op tot `total` — naïef per-LU afronden (PRD §10)
    zou onder- of overtellen geven. Wegingen hoeven niet op 1 te sommeren.
    """
    n = len(weights)
    if n == 0:
        return []
    weight_sum = sum(weights)
    if total <= 0 or weight_sum <= 0:
        return [0] * n

    exact = [total * w / weight_sum for w in weights]
    counts = [math.floor(x) for x in exact]
    leftover = total - sum(counts)
    # grootste resten eerst; bij gelijke rest wint de laagste index (stabiel)
    by_remainder = sorted(range(n), key=lambda i: (exact[i] - counts[i], -i), reverse=True)
    for i in by_remainder[:leftover]:
        counts[i] += 1
    return counts


def build_toetsset(store, project_id: int, total: int, reader_text: str, *, generate):
    """Stel een toetsset samen: verdeel `total` vragen over de leeruitkomsten
    naar weging, splits per leeruitkomst in mc/open op basis van het Bloom-
    niveau, genereer ze uit `reader_text` en sla ze op.

    `generate(text, *, type, n, bloom_level) -> list[ToetsVraag]` wordt
    geïnjecteerd (de AI-laag), zodat de orchestratie los testbaar blijft.
    Retourneert de opgeslagen ToetsVraag-objecten.
    """
    outcomes = store.list_learning_outcomes(project_id)
    if not outcomes:
        return []
    per_outcome = distribute_questions(total, [lo.weight for lo in outcomes])

    created = []
    for outcome, count in zip(outcomes, per_outcome):
        if count <= 0:
            continue
        mc_fraction = _MC_FRACTION.get(outcome.bloom_level, _DEFAULT_MC_FRACTION)
        n_mc, n_open = distribute_questions(count, [mc_fraction, 1 - mc_fraction])
        for kind, n in (("mc", n_mc), ("open", n_open)):
            if n <= 0:
                continue
            for vraag in generate(
                reader_text, type=kind, n=n, bloom_level=outcome.bloom_level or ""
            ):
                vraag.project_id = project_id
                vraag.learning_outcome_id = outcome.id
                created.append(store.add_toetsvraag(project_id, vraag))
    return created
