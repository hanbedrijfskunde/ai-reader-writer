from __future__ import annotations

import csv
import io

from app.models import LearningOutcome, ToetsVraag

_HEADER = [
    "leeruitkomst", "type", "bloom", "stam",
    "optie_a", "optie_b", "optie_c", "optie_d", "antwoord",
    "validiteit", "betrouwbaarheid", "techniek", "toelichting",
]


def toetsvragen_to_csv(
    vragen: list[ToetsVraag], outcomes: list[LearningOutcome]
) -> str:
    """Serialiseer toetsvragen naar CSV (één rij per vraag).

    mc-vragen vullen optie_a..d en de sleutel in `antwoord`; open vragen laten
    de optie-kolommen leeg en zetten het modelantwoord in `antwoord`. De
    leeruitkomst wordt als code opgenomen. Gebruikt het csv-module zodat
    komma's, aanhalingstekens en regeleinden in de stam correct worden
    ge-escaped.
    """
    code_by_id = {o.id: o.code for o in outcomes}
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_HEADER)
    for v in vragen:
        opts = (list(v.options) + ["", "", "", ""])[:4]
        writer.writerow([
            code_by_id.get(v.learning_outcome_id, ""),
            v.type,
            v.bloom_level or "",
            v.stem,
            opts[0], opts[1], opts[2], opts[3],
            v.answer,
            "" if v.validity is None else v.validity,
            "" if v.reliability is None else v.reliability,
            "" if v.technical is None else v.technical,
            v.notes or "",
        ])
    return buf.getvalue()
