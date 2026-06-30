import csv
import io

from app.models import LearningOutcome, ToetsVraag
from app.render.toets_csv import toetsvragen_to_csv

_HEADER = ["leeruitkomst", "type", "bloom", "stam", "optie_a", "optie_b",
           "optie_c", "optie_d", "antwoord", "validiteit", "betrouwbaarheid",
           "techniek", "toelichting"]


def _rows(text):
    return list(csv.reader(io.StringIO(text)))


def test_csv_header_and_mc_and_open_rows():
    outcomes = [LearningOutcome(id=1, project_id=1, code="LU1", title="x",
                                weight=1.0, bloom_level="Begrijpen")]
    vragen = [
        ToetsVraag(id=1, project_id=1, type="mc", stem="Wat is een TOM?",
                   learning_outcome_id=1, bloom_level="Begrijpen",
                   options=["A", "B", "C", "D"], answer="B"),
        ToetsVraag(id=2, project_id=1, type="open", stem="Leg uit.",
                   learning_outcome_id=1, bloom_level="Analyseren", options=[],
                   answer="Modelantwoord", validity=4, reliability=5,
                   technical=4, notes="ok"),
    ]
    rows = _rows(toetsvragen_to_csv(vragen, outcomes))
    assert rows[0] == _HEADER
    assert rows[1][0:4] == ["LU1", "mc", "Begrijpen", "Wat is een TOM?"]
    assert rows[1][4:8] == ["A", "B", "C", "D"]
    assert rows[1][8] == "B"
    assert rows[2][1] == "open"
    assert rows[2][4:8] == ["", "", "", ""]      # open question has no options
    assert rows[2][8] == "Modelantwoord"
    assert rows[2][9:13] == ["4", "5", "4", "ok"]


def test_csv_quotes_fields_with_commas_and_newlines():
    vragen = [ToetsVraag(id=1, project_id=1, type="open",
                         stem="Een, lastige\nvraag", answer="x")]
    rows = _rows(toetsvragen_to_csv(vragen, []))
    assert rows[1][3] == "Een, lastige\nvraag"   # round-trips intact


def test_csv_unknown_outcome_gives_blank_code():
    vragen = [ToetsVraag(id=1, project_id=1, type="mc", stem="x",
                         learning_outcome_id=99, options=["a", "b", "c", "d"],
                         answer="a")]
    rows = _rows(toetsvragen_to_csv(vragen, []))
    assert rows[1][0] == ""


def test_csv_empty_questions_is_header_only():
    rows = _rows(toetsvragen_to_csv([], []))
    assert rows == [_HEADER]
