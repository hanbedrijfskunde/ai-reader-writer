from __future__ import annotations

import math


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
