"""Run one impact assessment: prompt, validate, retry once, else mark unverified (IMP-4)."""

import logging
from dataclasses import dataclass, field

from regdiff_ai.llm.context import ImpactContext
from regdiff_ai.llm.prompt import build_messages
from regdiff_ai.llm.providers import LLMClient, LLMError
from regdiff_ai.llm.validator import LLMImpact, validate_output
from regdiff_common.logging import log_event

log = logging.getLogger(__name__)

DISCLAIMER = (
    "Automated assessment for decision support only. It is not legal advice, and every finding "
    "needs review by a qualified compliance professional."
)


@dataclass
class Assessment:
    verified: bool
    model: str
    summary: str
    summary_evidence_ids: list[str]
    affected: list[dict]
    impacts: list[dict]
    actions: list[dict]
    errors: list[str] = field(default_factory=list)


def assess(context: ImpactContext, llm: LLMClient, max_attempts: int = 2) -> Assessment:
    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        system, user = build_messages(context, previous_errors=errors or None)
        try:
            raw = llm.complete_json(system, user)
        except LLMError as exc:
            errors = [str(exc)]
            log_event(log, "impact_llm_failed", level=logging.WARNING, attempt=attempt, error=str(exc))
            continue
        result, errors = validate_output(raw, context)
        if result is not None:
            return _from_llm(result, context, llm.name)
        log_event(log, "impact_output_rejected", level=logging.WARNING, attempt=attempt, errors=errors)
    return _fallback(context, llm.name, errors)


def _from_llm(result: LLMImpact, context: ImpactContext, model: str) -> Assessment:
    reasons = {entry.item: entry for entry in result.affected}
    return Assessment(
        verified=True,
        model=model,
        summary=result.change_summary,
        summary_evidence_ids=result.summary_evidence_ids,
        affected=_affected(context, reasons),
        impacts=[entry.model_dump() for entry in result.potential_impact],
        actions=[entry.model_dump() for entry in result.recommended_actions],
    )


def _fallback(context: ImpactContext, model: str, errors: list[str]) -> Assessment:
    """Deterministic content so the report is still useful, clearly marked unverified."""
    change_ids = [e.id for e in context.evidence if e.role in ("old_clause", "new_clause")]
    return Assessment(
        verified=False,
        model=model,
        summary=f"Clause {context.clause_number} is {context.change_type.replace('_', ' ')}. "
        "The AI explanation could not be verified; review the evidence directly.",
        summary_evidence_ids=change_ids,
        affected=_affected(context, {}),
        impacts=[],
        actions=[{"action": "Review the change and the linked items manually.", "evidence_ids": change_ids}],
        errors=errors,
    )


def _affected(context: ImpactContext, reasons: dict) -> list[dict]:
    """Graph and retrieval decide *what* is affected and whether it is confirmed;
    the LLM only contributes the explanation."""
    affected = []
    for candidate in context.candidates:
        explanation = reasons.get(candidate.id)
        affected.append(
            {
                "id": candidate.id,
                "kind": candidate.kind,
                "label": candidate.label,
                "relation": candidate.relation,
                "found_by": candidate.found_by,
                "path": candidate.path,
                "reason": explanation.reason if explanation else None,
                "evidence_ids": explanation.evidence_ids if explanation else candidate.evidence_ids,
            }
        )
    return affected
