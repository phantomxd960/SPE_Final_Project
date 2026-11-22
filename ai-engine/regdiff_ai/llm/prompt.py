"""Prompt for the impact assessment. The input is passed as JSON so the
model sees exactly the evidence ids it is allowed to cite."""

import json

from regdiff_ai.llm.context import ImpactContext

INPUT_MARKER = "INPUT JSON:"

SYSTEM_PROMPT = """You are a regulatory change analyst at a financial institution.
You explain a regulation change that has already been detected; you never decide whether something changed.

Rules:
- Use only the evidence in the input. Every statement must cite one or more evidence ids (for example "E2").
- "affected" may only contain ids from candidate_affected_items. Do not invent policies, processes or controls.
- Never state that the institution or a policy is non-compliant, in breach, or violating the law.
  Describe what may need review instead.
- Be specific and concise. Answer with JSON only."""

OUTPUT_SHAPE = {
    "change_summary": "one or two sentences describing the change",
    "summary_evidence_ids": ["E1", "E2"],
    "affected": [{"item": "<candidate id>", "reason": "why it may be affected", "evidence_ids": ["E3"]}],
    "potential_impact": [{"statement": "possible operational impact", "evidence_ids": ["E2"]}],
    "recommended_actions": [{"action": "concrete next step for the compliance team", "evidence_ids": ["E2", "E3"]}],
}


def build_messages(context: ImpactContext, previous_errors: list[str] | None = None) -> tuple[str, str]:
    parts = [
        "Assess the impact of this regulation change.",
        f"Answer with a JSON object of exactly this shape:\n{json.dumps(OUTPUT_SHAPE, indent=2)}",
    ]
    if previous_errors:
        problems = "\n".join(f"- {error}" for error in previous_errors)
        parts.append(f"Your previous answer was rejected for these reasons; fix them:\n{problems}")
    parts.append(f"{INPUT_MARKER}\n{json.dumps(context.to_prompt_dict(), indent=2)}")
    return SYSTEM_PROMPT, "\n\n".join(parts)
