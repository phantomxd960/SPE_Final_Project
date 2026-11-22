"""Turn a text, Markdown or PDF file into numbered clauses.

Clauses are split by their numbering ("4.2.1 Institutions must ..."), never by
character count (ING-2). A depth-1 number with a short title and no full stop
("4. Transaction Reporting") is a section heading. Lines before the first
clause may carry metadata used by the dependency graph:

    Regulation: REG001
    Process: Transaction Monitoring
    Control: CTRL-TM-01 Daily threshold alerting
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}

_NUMBERED = re.compile(r"^(?:(?:clause|section|article|rule)\s+)?(\d+(?:\.\d+)*)[.)]?\s+(\S.*)$", re.IGNORECASE)
_METADATA = re.compile(r"^(regulation|process|control)\s*:\s*(.+)$", re.IGNORECASE)
_PAGE_MARKER = re.compile(r"^<!--\s*page\s+(\d+)\s*-->$", re.IGNORECASE)
_MARKDOWN_PREFIX = re.compile(r"^(?:#{1,6}\s+|[-*+]\s+|>\s+)")
_EMPHASIS = re.compile(r"(\*\*|__|`)")


class ParseError(Exception):
    """The document cannot be turned into clauses; retrying will not help."""


@dataclass
class ParsedClause:
    number: str
    section: str | None
    page: int
    text: str


@dataclass
class ParsedDocument:
    title: str | None
    clauses: list[ParsedClause]
    metadata: dict[str, list[str]] = field(default_factory=dict)


def parse_file(path: str | Path) -> ParsedDocument:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ParseError(f"Unsupported file type '{suffix}'. Use .txt, .md or .pdf.")
    if suffix == ".pdf":
        pages = _read_pdf_pages(path)
    else:
        pages = _split_text_pages(path.read_text(encoding="utf-8", errors="replace"))
    return parse_pages(pages)


def parse_text(text: str) -> ParsedDocument:
    return parse_pages(_split_text_pages(text))


def parse_pages(pages: list[tuple[int, str]]) -> ParsedDocument:
    title: str | None = None
    section: str | None = None
    metadata: dict[str, list[str]] = {}
    clauses: list[ParsedClause] = []
    current: ParsedClause | None = None
    seen_numbers: dict[str, int] = {}

    for page_number, page_text in pages:
        for raw_line in page_text.splitlines():
            is_heading = raw_line.lstrip().startswith("#")
            line = _clean_line(raw_line)
            if not line:
                continue

            numbered = _NUMBERED.match(line)
            if numbered and _starts_like_a_clause(numbered.group(2)):
                number, body = numbered.group(1), numbered.group(2).strip()
                if _is_section_heading(number, body):
                    section = body
                    current = None
                    continue
                count = seen_numbers.get(number, 0) + 1
                seen_numbers[number] = count
                unique_number = number if count == 1 else f"{number} ({count})"
                current = ParsedClause(number=unique_number, section=section, page=page_number, text=body)
                clauses.append(current)
                continue

            meta = _METADATA.match(line)
            if meta and not clauses:
                metadata.setdefault(meta.group(1).lower(), []).append(meta.group(2).strip())
                continue

            if is_heading:
                if title is None and not clauses:
                    title = line
                else:
                    section = line
                    current = None
                continue

            if current is not None:
                current.text = f"{current.text} {line}"
            elif title is None and not clauses:
                title = line

    if not clauses:
        raise ParseError("No numbered clauses found. Clauses must start with a number such as '4.2.1'.")
    return ParsedDocument(title=title, clauses=clauses, metadata=metadata)


def _clean_line(line: str) -> str:
    line = line.strip()
    line = _MARKDOWN_PREFIX.sub("", line)
    line = _EMPHASIS.sub("", line)
    return line.strip()


def _starts_like_a_clause(body: str) -> bool:
    # "5 business days." on a wrapped line is a continuation, not clause 5.
    return body[:1].isupper() or body[:1] in "(\"'"


def _is_section_heading(number: str, body: str) -> bool:
    return "." not in number and len(body) <= 80 and not body.endswith((".", ";", ":"))


def _split_text_pages(text: str) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    page_number, buffer = 1, []
    for line in text.replace("\f", "\n<!-- page next -->\n").splitlines():
        stripped = line.strip()
        marker = _PAGE_MARKER.match(stripped)
        if marker or stripped.lower() == "<!-- page next -->":
            if buffer:
                pages.append((page_number, "\n".join(buffer)))
            page_number = int(marker.group(1)) if marker else page_number + 1
            buffer = []
            continue
        buffer.append(line)
    if buffer:
        pages.append((page_number, "\n".join(buffer)))
    return pages


def _read_pdf_pages(path: Path) -> list[tuple[int, str]]:
    import pymupdf  # imported lazily: only PDF uploads need it

    try:
        with pymupdf.open(path) as pdf:
            pages = [(index + 1, page.get_text("text")) for index, page in enumerate(pdf)]
    except Exception as exc:  # corrupt or encrypted PDF
        raise ParseError(f"Could not read PDF: {exc}") from exc
    if not any(text.strip() for _, text in pages):
        raise ParseError("The PDF has no extractable text (scanned PDFs and OCR are out of scope).")
    return pages
