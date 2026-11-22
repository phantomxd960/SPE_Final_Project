"""Extract the facts whose change makes a clause *substantially* changed (CHG-3, CHG-4):
amounts with currency, percentages, durations, dates, other numbers and the
obligation level of modal verbs (must / should / may / must not)."""

import re
from collections import Counter
from dataclasses import dataclass, field

_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"

_REFERENCE = re.compile(r"\b(?:clauses?|sections?|articles?|paragraphs?|rules?)\s+\d+(?:\.\d+)*", re.IGNORECASE)
_DATE = re.compile(
    rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}}\b|\b(?:{_MONTHS})\s+\d{{1,2}},\s*\d{{4}}\b",
    re.IGNORECASE,
)
_AMOUNT = re.compile(
    r"(?P<cur1>EUR|USD|GBP|INR|€|\$|£|₹|Rs\.?)\s?(?P<amt1>\d[\d,]*(?:\.\d+)?)(?:\s?(?P<mul1>thousand|million|billion|bn|k|m)\b)?"
    r"|(?P<amt2>\d[\d,]*(?:\.\d+)?)(?:\s?(?P<mul2>thousand|million|billion))?\s?(?P<cur2>EUR|USD|GBP|INR|euros?|dollars?|rupees?|pounds?)\b",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"\b(\d+(?:\.\d+)?)\s?(?:%|per\s?cent\b|percent\b)", re.IGNORECASE)
_DURATION = re.compile(r"\b(\d+)\s+(?:(business|working|calendar)\s+)?(day|hour|week|month|year)s?\b", re.IGNORECASE)
_NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
_MODAL = re.compile(
    r"\b(must not|shall not|may not|should not|must|shall|should|may|(?:is|are) required to|(?:is|are) prohibited)\b",
    re.IGNORECASE,
)

_CURRENCY = {
    "€": "EUR",
    "$": "USD",
    "£": "GBP",
    "₹": "INR",
    "rs": "INR",
    "rs.": "INR",
    "euro": "EUR",
    "euros": "EUR",
    "dollar": "USD",
    "dollars": "USD",
    "rupee": "INR",
    "rupees": "INR",
    "pound": "GBP",
    "pounds": "GBP",
}
_MULTIPLIER = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
_OBLIGATION = {
    "must": "mandatory",
    "shall": "mandatory",
    "is required to": "mandatory",
    "are required to": "mandatory",
    "should": "recommended",
    "may": "permitted",
    "must not": "prohibited",
    "shall not": "prohibited",
    "may not": "prohibited",
    "is prohibited": "prohibited",
    "are prohibited": "prohibited",
    "should not": "discouraged",
}

FACT_KINDS = ("amount", "percentage", "duration", "date", "number", "obligation")


@dataclass
class Facts:
    values: dict[str, list[str]] = field(default_factory=lambda: {kind: [] for kind in FACT_KINDS})


def extract_facts(text: str) -> Facts:
    facts = Facts()
    remaining = _REFERENCE.sub(" ", text)  # "see clause 4.2.1" is a reference, not a number

    def take(pattern: re.Pattern, kind: str, render) -> None:
        nonlocal remaining
        for match in pattern.finditer(remaining):
            facts.values[kind].append(render(match))
        remaining = pattern.sub(" ", remaining)

    take(_DATE, "date", lambda m: " ".join(m.group(0).lower().split()))
    take(_AMOUNT, "amount", _render_amount)
    take(_PERCENT, "percentage", lambda m: f"{_number(m.group(1)):g}%")
    take(_DURATION, "duration", _render_duration)
    take(_NUMBER, "number", lambda m: f"{_number(m.group(0)):g}")
    # Scanned after dates are removed, so the month "May" is not read as a modal verb.
    facts.values["obligation"] = [_OBLIGATION[m.group(1).lower()] for m in _MODAL.finditer(remaining)]
    return facts


def compare_facts(old_text: str, new_text: str) -> list[dict]:
    """Differences per fact kind, e.g. {"kind": "amount", "old": ["EUR 10000"], "new": ["EUR 5000"]}."""
    old, new = extract_facts(old_text).values, extract_facts(new_text).values
    differences = []
    for kind in FACT_KINDS:
        if Counter(old[kind]) != Counter(new[kind]):
            removed = list((Counter(old[kind]) - Counter(new[kind])).elements())
            added = list((Counter(new[kind]) - Counter(old[kind])).elements())
            differences.append({"kind": kind, "old": removed, "new": added})
    return differences


def _number(raw: str) -> float:
    return float(raw.replace(",", ""))


def _render_amount(match: re.Match) -> str:
    currency = (match.group("cur1") or match.group("cur2")).lower()
    currency = _CURRENCY.get(currency, currency.upper())
    amount = _number(match.group("amt1") or match.group("amt2"))
    multiplier = (match.group("mul1") or match.group("mul2") or "").lower()
    amount *= _MULTIPLIER.get(multiplier, 1)
    return f"{currency} {amount:,.2f}".replace(".00", "")


def _render_duration(match: re.Match) -> str:
    count, qualifier, unit = match.group(1), (match.group(2) or "").lower(), match.group(3).lower()
    return " ".join(part for part in (count, qualifier, unit + ("s" if count != "1" else "")) if part)
