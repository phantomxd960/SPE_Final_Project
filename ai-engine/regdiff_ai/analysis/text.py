"""Small text helpers shared by alignment and classification."""

import difflib
import hashlib
import re

_WORDS = re.compile(r"\w+(?:[.,]\w+)*")
_TOKENS = re.compile(r"\S+|\s+")


def normalize(text: str) -> str:
    return " ".join(text.split())


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()


def words(text: str) -> list[str]:
    return _WORDS.findall(text.lower())


def similarity(a: str, b: str) -> float:
    """Word-level difflib ratio in [0, 1]."""
    return difflib.SequenceMatcher(None, words(a), words(b), autojunk=False).ratio()


def word_overlap(a: str, b: str) -> float:
    """Jaccard overlap of the word sets."""
    wa, wb = set(words(a)), set(words(b))
    return len(wa & wb) / len(wa | wb) if wa | wb else 1.0


def word_diff(old: str, new: str) -> list[list[str]]:
    """Word-level diff as [[op, text], ...] with op in equal | delete | insert."""
    a, b = _TOKENS.findall(normalize(old)), _TOKENS.findall(normalize(new))
    ops: list[list[str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            _append(ops, "equal", "".join(a[i1:i2]))
        else:
            if i2 > i1:
                _append(ops, "delete", "".join(a[i1:i2]))
            if j2 > j1:
                _append(ops, "insert", "".join(b[j1:j2]))
    return ops


def _append(ops: list[list[str]], op: str, text: str) -> None:
    if ops and ops[-1][0] == op:
        ops[-1][1] += text
    else:
        ops.append([op, text])
