"""Validate LLM output before it is stored (IMP-3 to IMP-5).

An answer is rejected when it is not valid JSON of the expected shape, cites
evidence that was not supplied, names an affected item that was not a
candidate, or states legal non-compliance.
"""

import json
import re

from pydantic import BaseModel, Field, ValidationError

from regdiff_ai.llm.context import ImpactContext

_FORBIDDEN = re.compile(
    r"\b(non-?compliant|non-?compliance|in breach of|breaches the|violat\w*|unlawful|illegal)\b", re.IGNORECASE
)
_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


class _Cited(BaseModel):
    evidence_ids: list[str] = Field(min_length=1)


class AffectedItem(_Cited):
    item: str
    reason: str


class ImpactStatement(_Cited):
    statement: str


class RecommendedAction(_Cited):
    action: str


class LLMImpact(BaseModel):
    change_summary: str = Field(min_length=1)
    summary_evidence_ids: list[str] = Field(min_length=1)
    affected: list[AffectedItem] = Field(default_factory=list)
    potential_impact: list[ImpactStatement] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(min_length=1)


def validate_output(raw: str, context: ImpactContext) -> tuple[LLMImpact | None, list[str]]:
    try:
        data = json.loads(_CODE_FENCE.sub("", raw.strip()))
        result = LLMImpact.model_validate(data)
    except json.JSONDecodeError as exc:
        return None, [f"Output is not valid JSON: {exc.msg}"]
    except ValidationError as exc:
        return None, [f"Output does not match the schema: {error['loc']} {error['msg']}" for error in exc.errors()]

    errors: list[str] = []
    allowed_evidence, allowed_items = context.evidence_ids, context.candidate_ids

    cited = list(result.summary_evidence_ids)
    texts = [result.change_summary]
    for group in (result.affected, result.potential_impact, result.recommended_actions):
        for entry in group:
            cited.extend(entry.evidence_ids)
    texts += [a.reason for a in result.affected]
    texts += [p.statement for p in result.potential_impact]
    texts += [r.action for r in result.recommended_actions]

    unknown = sorted(set(cited) - allowed_evidence)
    if unknown:
        errors.append(f"Cites evidence that was not supplied: {', '.join(unknown)}")
    invented = sorted({a.item for a in result.affected} - allowed_items)
    if invented:
        errors.append(f"Lists affected items that are not candidates: {', '.join(invented)}")
    for text in texts:
        if _FORBIDDEN.search(text):
            errors.append(f"States legal non-compliance, which is not allowed: '{text[:80]}'")
            break
    return (result if not errors else None), errors
