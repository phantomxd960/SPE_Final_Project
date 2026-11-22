from regdiff_ai.analysis.facts import compare_facts, extract_facts


def test_amounts_are_normalised_across_formats():
    values = extract_facts("Report EUR 10,000 or €2 million, or 500 dollars.").values
    assert values["amount"] == ["EUR 10,000", "EUR 2,000,000", "USD 500"]


def test_percentages_durations_and_dates():
    values = extract_facts("Within 5 business days, 2.5% of volume, from 1 March 2026.").values
    assert values["duration"] == ["5 business days"]
    assert values["percentage"] == ["2.5%"]
    assert values["date"] == ["1 march 2026"]


def test_clause_references_are_not_numbers():
    assert extract_facts("As set out in clause 4.2.1, staff must act.").values["number"] == []


def test_obligation_levels():
    values = extract_facts("Firms must report and should notify; they may not delay.").values
    assert values["obligation"] == ["mandatory", "recommended", "prohibited"]


def test_lowered_threshold_is_a_difference():
    differences = compare_facts(
        "Institutions must report transactions of EUR 10,000 or more.",
        "Institutions must report transactions of EUR 5,000 or more.",
    )
    assert differences == [{"kind": "amount", "old": ["EUR 10,000"], "new": ["EUR 5,000"]}]


def test_obligation_change_is_a_difference():
    differences = compare_facts("Firms should keep records.", "Firms must keep records.")
    assert differences == [{"kind": "obligation", "old": ["recommended"], "new": ["mandatory"]}]


def test_wording_change_without_facts_is_not_a_difference():
    assert compare_facts("Firms must keep records.", "Institutions must retain records.") == []
