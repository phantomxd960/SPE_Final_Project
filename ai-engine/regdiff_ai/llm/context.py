"""Everything the LLM may use for one impact assessment (IMP-2)."""

from dataclasses import asdict, dataclass, field


@dataclass
class Evidence:
    id: str  # "E1", "E2", ...
    role: str  # old_clause | new_clause | dependent_clause | related_passage
    doc_code: str
    doc_title: str
    version_label: str
    clause_number: str
    page: int
    text: str
    clause_id: int | None = None


@dataclass
class Candidate:
    """An item that may be affected: found by graph traversal or by retrieval."""

    id: str  # graph node key, e.g. "policy:POL-TM"
    kind: str  # policy | process | control
    label: str
    relation: str  # confirmed | inferred
    found_by: str  # graph | retrieval
    path: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class ImpactContext:
    doc_code: str
    doc_title: str
    clause_number: str
    old_version: str | None
    new_version: str | None
    change_type: str
    differences: list[dict]
    evidence: list[Evidence]
    candidates: list[Candidate]

    @property
    def evidence_ids(self) -> set[str]:
        return {item.id for item in self.evidence}

    @property
    def candidate_ids(self) -> set[str]:
        return {item.id for item in self.candidates}

    def to_prompt_dict(self) -> dict:
        return {
            "change": {
                "regulation": f"{self.doc_code} ({self.doc_title})",
                "clause": self.clause_number,
                "old_version": self.old_version,
                "new_version": self.new_version,
                "change_type": self.change_type,
                "deterministic_differences": self.differences,
            },
            "evidence": [{k: v for k, v in asdict(item).items() if k != "clause_id"} for item in self.evidence],
            "candidate_affected_items": [
                {k: v for k, v in asdict(item).items() if k != "path"} for item in self.candidates
            ],
        }
