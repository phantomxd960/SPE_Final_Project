"""Align old and new clauses (CHG-1, Section 8.1).

Passes, each working only on clauses still unmatched:
  1. same number and identical text        -> unchanged
  2. identical text under another number   -> renumbered
  3. same number (unless the texts are unrelated, which signals a shift)
  4. greedy best text similarity above the threshold
Whatever is left is deleted (old) or added (new).
"""

from dataclasses import dataclass

from regdiff_ai.analysis.text import normalize, similarity

UNRELATED_BELOW = 0.30


@dataclass(frozen=True)
class ClauseInput:
    id: int
    number: str
    text: str
    embedding: tuple[float, ...] | None = None


@dataclass(frozen=True)
class AlignedPair:
    old: ClauseInput | None
    new: ClauseInput | None
    method: str  # exact | text | number | similarity | unmatched


def align(old: list[ClauseInput], new: list[ClauseInput], min_similarity: float = 0.60) -> list[AlignedPair]:
    old_left = dict(enumerate(old))
    new_left = dict(enumerate(new))
    matched: list[tuple[int, int, str]] = []  # (old index, new index, method)

    def match(predicate, method: str) -> None:
        for j, new_clause in list(new_left.items()):
            for i, old_clause in list(old_left.items()):
                if predicate(old_clause, new_clause):
                    matched.append((i, j, method))
                    del old_left[i], new_left[j]
                    break

    match(lambda o, n: o.number == n.number and normalize(o.text) == normalize(n.text), "exact")
    match(lambda o, n: normalize(o.text) == normalize(n.text), "text")
    match(lambda o, n: o.number == n.number and similarity(o.text, n.text) >= UNRELATED_BELOW, "number")

    candidates = sorted(
        ((similarity(o.text, n.text), i, j) for i, o in old_left.items() for j, n in new_left.items()),
        reverse=True,
    )
    for score, i, j in candidates:
        if score < min_similarity:
            break
        if i in old_left and j in new_left:
            matched.append((i, j, "similarity"))
            del old_left[i], new_left[j]

    return _in_reading_order(old, new, matched, old_left, new_left)


def _in_reading_order(old, new, matched, old_left, new_left) -> list[AlignedPair]:
    """Order pairs by the new document; deleted clauses sit after their old predecessor."""
    keyed: list[tuple[float, AlignedPair]] = []
    for i, j, method in matched:
        keyed.append((j, AlignedPair(old[i], new[j], method)))
    for j in new_left:
        keyed.append((j, AlignedPair(None, new[j], "unmatched")))
    for i in old_left:
        predecessors = [mj for mi, mj, _ in matched if mi < i]
        position = max(predecessors) + 0.5 if predecessors else -0.5 + i / 1000
        keyed.append((position, AlignedPair(old[i], None, "unmatched")))
    return [pair for _, pair in sorted(keyed, key=lambda item: item[0])]
