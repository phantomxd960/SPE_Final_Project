import json

from regdiff_ai.llm.assess import assess
from regdiff_ai.llm.context import Candidate, Evidence, ImpactContext
from regdiff_ai.llm.providers import MockLLM
from regdiff_ai.llm.validator import validate_output


def make_context() -> ImpactContext:
    def ev(eid, role, code, number, text):
        return Evidence(eid, role, code, code, "1.0", number, 1, text, clause_id=int(eid[1:]))

    return ImpactContext(
        doc_code="REG001",
        doc_title="Transaction Reporting Regulation",
        clause_number="4.2.1",
        old_version="1.0",
        new_version="2.0",
        change_type="substantially_changed",
        differences=[{"kind": "amount", "old": ["EUR 10,000"], "new": ["EUR 5,000"]}],
        evidence=[
            ev("E1", "old_clause", "REG001", "4.2.1", "Report transactions of EUR 10,000 or more."),
            ev("E2", "new_clause", "REG001", "4.2.1", "Report transactions of EUR 5,000 or more."),
            ev("E3", "dependent_clause", "POL-TM", "3.1", "Alerts follow clause 4.2.1."),
        ],
        candidates=[
            Candidate(
                "policy:POL-TM",
                "policy",
                "Transaction Monitoring Policy",
                "confirmed",
                "graph",
                ["reg_clause:REG001#4.2.1", "policy_clause:POL-TM#3.1", "policy:POL-TM"],
                ["E3"],
            )
        ],
    )


class ScriptedLLM:
    name = "scripted"

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.calls = 0

    def complete_json(self, system: str, user: str) -> str:
        self.calls += 1
        return self.answers.pop(0)


def valid_answer(**overrides) -> str:
    answer = {
        "change_summary": "The reporting threshold drops from EUR 10,000 to EUR 5,000.",
        "summary_evidence_ids": ["E1", "E2"],
        "affected": [{"item": "policy:POL-TM", "reason": "Its alert rule cites clause 4.2.1.", "evidence_ids": ["E3"]}],
        "potential_impact": [{"statement": "More transactions will be reported.", "evidence_ids": ["E2"]}],
        "recommended_actions": [{"action": "Lower the alert threshold to EUR 5,000.", "evidence_ids": ["E2", "E3"]}],
    }
    answer.update(overrides)
    return json.dumps(answer)


def test_mock_llm_output_passes_validation():
    result = assess(make_context(), MockLLM())
    assert result.verified
    assert result.affected[0]["relation"] == "confirmed"
    assert "EUR 10,000" in result.summary


def test_valid_answer_is_accepted_in_code_fences():
    result, errors = validate_output(f"```json\n{valid_answer()}\n```", make_context())
    assert errors == [] and result is not None


def test_citing_unknown_evidence_is_rejected():
    _, errors = validate_output(valid_answer(summary_evidence_ids=["E9"]), make_context())
    assert any("E9" in error for error in errors)


def test_invented_policy_is_rejected():
    affected = [{"item": "policy:POL-X", "reason": "made up", "evidence_ids": ["E2"]}]
    _, errors = validate_output(valid_answer(affected=affected), make_context())
    assert any("POL-X" in error for error in errors)


def test_claim_of_non_compliance_is_rejected():
    _, errors = validate_output(valid_answer(change_summary="The policy is now non-compliant."), make_context())
    assert errors


def test_bad_answer_is_retried_once_then_accepted():
    llm = ScriptedLLM("not json", valid_answer())
    result = assess(make_context(), llm)
    assert result.verified and llm.calls == 2


def test_two_bad_answers_give_an_unverified_report():
    llm = ScriptedLLM("not json", valid_answer(summary_evidence_ids=["E42"]))
    result = assess(make_context(), llm)
    assert not result.verified
    assert result.errors and result.affected[0]["id"] == "policy:POL-TM"
