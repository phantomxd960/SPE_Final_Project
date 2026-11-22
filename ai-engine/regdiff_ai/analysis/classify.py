"""Classify an aligned clause pair (CHG-2 to CHG-5, Section 8.1)."""

from dataclasses import dataclass, field

from regdiff_ai.analysis.align import AlignedPair
from regdiff_ai.analysis.facts import compare_facts
from regdiff_ai.analysis.text import normalize, similarity, word_diff, word_overlap
from regdiff_common.embeddings import cosine

ADDED = "added"
DELETED = "deleted"
UNCHANGED = "unchanged"
RENUMBERED = "renumbered"
SUBSTANTIAL = "substantially_changed"
EQUIVALENT = "semantically_equivalent"
MODIFIED = "modified"

CHANGE_TYPES = (ADDED, DELETED, MODIFIED, RENUMBERED, EQUIVALENT, SUBSTANTIAL, UNCHANGED)
SIGNIFICANT = frozenset({ADDED, DELETED, MODIFIED, SUBSTANTIAL})


@dataclass(frozen=True)
class Thresholds:
    renumbered_min_similarity: float = 0.95
    equivalent_min_embedding_similarity: float = 0.92
    equivalent_max_word_overlap: float = 0.70


@dataclass
class ChangeResult:
    change_type: str
    similarity: float
    confidence: float
    numeric_changes: list[dict] = field(default_factory=list)
    text_diff: list[list[str]] = field(default_factory=list)

    @property
    def significant(self) -> bool:
        return self.change_type in SIGNIFICANT


def classify(pair: AlignedPair, thresholds: Thresholds = Thresholds()) -> ChangeResult:
    old, new = pair.old, pair.new
    if old is None and new is not None:
        return ChangeResult(ADDED, 0.0, 0.9, text_diff=[["insert", normalize(new.text)]])
    if new is None and old is not None:
        return ChangeResult(DELETED, 0.0, 0.9, text_diff=[["delete", normalize(old.text)]])
    assert old is not None and new is not None

    text_similarity = round(similarity(old.text, new.text), 4)
    diff = word_diff(old.text, new.text)
    renumbered = old.number != new.number

    if normalize(old.text) == normalize(new.text):
        change_type = RENUMBERED if renumbered else UNCHANGED
        return ChangeResult(change_type, 1.0, 1.0, text_diff=diff)

    facts = compare_facts(old.text, new.text)
    if facts:
        # A changed amount, deadline or obligation level is substantial even when
        # the wording is almost identical (CHG-4).
        return ChangeResult(SUBSTANTIAL, text_similarity, 0.95, numeric_changes=facts, text_diff=diff)

    if renumbered and text_similarity >= thresholds.renumbered_min_similarity:
        return ChangeResult(RENUMBERED, text_similarity, text_similarity, text_diff=diff)

    if old.embedding and new.embedding:
        meaning = cosine(list(old.embedding), list(new.embedding))
        if (
            meaning >= thresholds.equivalent_min_embedding_similarity
            and word_overlap(old.text, new.text) <= thresholds.equivalent_max_word_overlap
        ):
            return ChangeResult(EQUIVALENT, text_similarity, round(meaning, 4), text_diff=diff)

    return ChangeResult(MODIFIED, text_similarity, round(0.6 + 0.4 * (1 - text_similarity), 4), text_diff=diff)
