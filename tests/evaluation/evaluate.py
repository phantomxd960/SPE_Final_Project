"""Evaluate change detection against the hand-labelled clause pairs (SRS Section 10).

Runs the real parser, alignment and classification, with the real embedding model
when it is available. Easiest inside the ai-worker image, which ships the model:

    docker run --rm -v "$PWD:/repo" -w /repo <dockerhub-user>/regulationdiff-ai-worker:latest \
        python tests/evaluation/evaluate.py --output docs/evaluation.md

Not collected by pytest (no test_ prefix); the unit tests cover the same code paths.
"""

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

from regdiff_ai.analysis.align import ClauseInput, align
from regdiff_ai.analysis.classify import CHANGE_TYPES, Thresholds, classify
from regdiff_ai.ingestion import parse_file
from regdiff_common.config import get_settings
from regdiff_common.embeddings import get_embedder

ROOT = Path(__file__).resolve().parents[2]
LABELS = Path(__file__).with_name("labels.json")


def inputs(path: Path, embedder, offset: int) -> list[ClauseInput]:
    clauses = parse_file(path).clauses
    vectors = embedder.embed([c.text for c in clauses])
    return [
        ClauseInput(id=offset + i, number=c.number, text=c.text, embedding=tuple(v))
        for i, (c, v) in enumerate(zip(clauses, vectors, strict=True))
    ]


def evaluate_pair(pair: dict, embedder, thresholds: Thresholds) -> list[dict]:
    old = inputs(ROOT / pair["old"], embedder, 0)
    new = inputs(ROOT / pair["new"], embedder, 10_000)
    predicted = {}
    for aligned in align(old, new, get_settings().align_min_similarity):
        result = classify(aligned, thresholds)
        key = aligned.new.number if aligned.new else f"old:{aligned.old.number}"
        predicted[key] = (result.change_type, aligned.old.number if aligned.old else None)

    rows = []
    for key, label in pair["expected"].items():
        expected_type, expected_old = label if isinstance(label, list) else (label, None)
        if expected_old is None and expected_type not in ("added", "deleted"):
            expected_old = key  # same clause number in both versions
        if expected_type == "deleted":
            expected_old = key.removeprefix("old:")
        predicted_type, predicted_old = predicted.get(key, ("(missing)", None))
        rows.append(
            {
                "pair": pair["name"],
                "clause": key,
                "expected": expected_type,
                "predicted": predicted_type,
                "aligned_ok": predicted_old == expected_old,
            }
        )
    return rows


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.2f} ({numerator}/{denominator})" if denominator else "n/a"


def report(rows: list[dict], embedder_name: str, thresholds: Thresholds, notes: list[str]) -> str:
    changed = [r for r in rows if r["expected"] != "unchanged"]
    flagged = [r for r in rows if r["predicted"] != "unchanged"]
    true_positive = sum(1 for r in changed if r["predicted"] != "unchanged")
    correct_type = sum(1 for r in rows if r["predicted"] == r["expected"])
    substantial = [r for r in rows if r["expected"] == "substantially_changed"]
    substantial_hit = sum(1 for r in substantial if r["predicted"] == "substantially_changed")
    aligned = sum(1 for r in rows if r["aligned_ok"])
    precision, recall = (
        true_positive / len(flagged) if flagged else 0,
        true_positive / len(changed) if changed else 0,
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

    lines = [
        "# Change-detection evaluation",
        "",
        f"Generated {date.today().isoformat()} by `tests/evaluation/evaluate.py` from `tests/evaluation/labels.json`.",
        f"Embedding model: `{embedder_name}`. Thresholds: renumbered ≥ {thresholds.renumbered_min_similarity}, "
        f"semantically equivalent ≥ {thresholds.equivalent_min_embedding_similarity} embedding similarity "
        f"with word overlap ≤ {thresholds.equivalent_max_word_overlap}.",
        "",
        f"Data: {len({r['pair'] for r in rows})} regulation version pairs, {len(rows)} hand-labelled clause pairs "
        f"({len(changed)} changed, {len(rows) - len(changed)} unchanged).",
        "",
        "## Results",
        "",
        "| Metric | Result | Target (SRS §10) |",
        "| --- | --- | --- |",
        f"| Change detection precision (flagged clauses that really changed) | {ratio(true_positive, len(flagged))} "
        "| ≥ 0.85 |",
        f"| Change detection recall (real changes that were flagged) | {ratio(true_positive, len(changed))} | ≥ 0.85 |",
        f"| Change detection F1 | {f1:.2f} | |",
        f"| Change type accuracy (exact type) | {ratio(correct_type, len(rows))} | |",
        f"| Substantial changes caught (amount, rate, date, obligation) | {ratio(substantial_hit, len(substantial))} "
        "| |",
        f"| Clause alignment accuracy | {ratio(aligned, len(rows))} | |",
        "",
        "## Confusion by change type",
        "",
        "Rows are the labelled type, columns the predicted type.",
        "",
    ]
    types = [t for t in CHANGE_TYPES if any(r["expected"] == t or r["predicted"] == t for r in rows)]
    counts = Counter((r["expected"], r["predicted"]) for r in rows)
    lines.append("| labelled \\ predicted | " + " | ".join(types) + " |")
    lines.append("| --- |" + " --- |" * len(types))
    for expected in types:
        if any(r["expected"] == expected for r in rows):
            cells = [str(counts[(expected, p)] or "·") for p in types]
            lines.append(f"| **{expected}** | " + " | ".join(cells) + " |")

    mistakes = [r for r in rows if r["predicted"] != r["expected"] or not r["aligned_ok"]]
    lines += ["", "## Disagreements", ""]
    if not mistakes:
        lines.append("None: every labelled clause pair was aligned and classified as expected.")
    else:
        lines.append("| Pair | Clause | Labelled | Predicted | Aligned to the right clause |")
        lines.append("| --- | --- | --- | --- | --- |")
        for r in mistakes:
            lines.append(
                f"| {r['pair']} | {r['clause']} | {r['expected']} | {r['predicted']} | "
                f"{'yes' if r['aligned_ok'] else 'no'} |"
            )
    if notes:
        lines += ["", "## Notes", ""] + [f"- {note}" for note in notes]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", help="write the Markdown report here (default: print it)")
    args = parser.parse_args()

    settings = get_settings()
    thresholds = Thresholds(
        settings.renumbered_min_similarity,
        settings.equivalent_min_embedding_similarity,
        settings.equivalent_max_word_overlap,
    )
    embedder = get_embedder()
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    rows = [row for pair in labels["pairs"] for row in evaluate_pair(pair, embedder, thresholds)]
    text = report(rows, embedder.name, thresholds, labels.get("notes", []))
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    print(text)


if __name__ == "__main__":
    main()
