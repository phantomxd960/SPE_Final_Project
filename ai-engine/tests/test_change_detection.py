from regdiff_ai.analysis.align import ClauseInput, align
from regdiff_ai.analysis.classify import (
    ADDED,
    DELETED,
    EQUIVALENT,
    MODIFIED,
    RENUMBERED,
    SUBSTANTIAL,
    UNCHANGED,
    classify,
)


def clauses(*items: tuple[str, str]) -> list[ClauseInput]:
    return [ClauseInput(id=index, number=number, text=text) for index, (number, text) in enumerate(items)]


OLD = clauses(
    ("4.2.1", "Institutions must report cash transactions of EUR 10,000 or more."),
    ("4.2.2", "Reports are submitted electronically to the authority."),
    ("4.3", "Records of reports are retained by the compliance team."),
    ("4.4", "Staff receive annual training on reporting."),
)
NEW = clauses(
    ("4.2.1", "Institutions must report cash transactions of EUR 5,000 or more."),
    ("4.2.2", "Reports are submitted electronically to the authority."),
    ("4.3", "Suspicious patterns are escalated to the money laundering officer."),
    ("4.4", "Records of reports are retained by the compliance team."),
)


def result_by_new_number(pairs):
    return {(p.new.number if p.new else f"old:{p.old.number}"): classify(p).change_type for p in pairs}


def test_alignment_and_classification_of_the_demo_scenario():
    types = result_by_new_number(align(OLD, NEW))
    assert types["4.2.1"] == SUBSTANTIAL  # threshold lowered (CHG-4)
    assert types["4.2.2"] == UNCHANGED
    assert types["4.4"] == RENUMBERED  # old 4.3 moved down after an insertion
    assert types["4.3"] == ADDED
    assert types["old:4.4"] == DELETED


def test_pairs_follow_reading_order_of_the_new_document():
    pairs = align(OLD, NEW)
    numbers = [p.new.number if p.new else f"old:{p.old.number}" for p in pairs]
    assert numbers.index("4.2.1") < numbers.index("4.3") < numbers.index("4.4")


def test_reworded_clause_is_modified():
    pair = align(
        clauses(("1.1", "The board approves the reporting policy every year.")),
        clauses(("1.1", "The board reviews and approves the reporting policy every year.")),
    )[0]
    result = classify(pair)
    assert result.change_type == MODIFIED
    assert result.text_diff == [
        ["equal", "The board"],
        ["insert", " reviews and"],
        ["equal", " approves the reporting policy every year."],
    ]


def test_high_wording_similarity_does_not_hide_a_numeric_change():
    pair = align(
        clauses(("2.1", "Reports are due within 10 business days.")),
        clauses(("2.1", "Reports are due within 3 business days.")),
    )[0]
    result = classify(pair)
    assert result.change_type == SUBSTANTIAL
    assert result.numeric_changes[0]["kind"] == "duration"


def test_semantically_equivalent_uses_embeddings():
    same_meaning = (1.0, 0.0, 0.0)
    pair = align(
        [ClauseInput(1, "3.1", "Firms keep transaction logs.", same_meaning)],
        [ClauseInput(2, "3.1", "Institutions retain records of every payment they process.", same_meaning)],
        min_similarity=0.0,
    )[0]
    assert classify(pair).change_type == EQUIVALENT
