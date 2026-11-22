import pytest

from regdiff_ai.ingestion import ParseError, parse_text

DOCUMENT = """# REG001 Transaction Reporting Regulation
Version 2.0 · Effective 2026-01-01

## 4. Transaction Reporting

4.2.1 Institutions must report every cash transaction of EUR 5,000 or more
within 5 business days.
4.2.2 Reports are submitted electronically.

<!-- page 2 -->
## 5. Record Keeping
5.1 Records must be kept for 5 years.
"""


def test_splits_by_clause_number_and_tracks_sections_and_pages():
    parsed = parse_text(DOCUMENT)
    assert parsed.title == "REG001 Transaction Reporting Regulation"
    assert [c.number for c in parsed.clauses] == ["4.2.1", "4.2.2", "5.1"]
    first = parsed.clauses[0]
    assert first.section == "Transaction Reporting"
    assert first.text.endswith("within 5 business days.")  # wrapped line joined, not a new clause
    assert parsed.clauses[2].page == 2 and parsed.clauses[2].section == "Record Keeping"


def test_header_metadata_is_collected():
    parsed = parse_text(
        "# Policy\nRegulation: REG001\nProcess: Transaction Monitoring\nControl: CTRL-1\n\n1.1 Staff must comply."
    )
    assert parsed.metadata == {"regulation": ["REG001"], "process": ["Transaction Monitoring"], "control": ["CTRL-1"]}


def test_duplicate_numbers_are_kept_apart():
    parsed = parse_text("1.1 First text.\n1.1 Second text.")
    assert [c.number for c in parsed.clauses] == ["1.1", "1.1 (2)"]


def test_document_without_clauses_is_rejected():
    with pytest.raises(ParseError):
        parse_text("Just a paragraph with no numbering.")
