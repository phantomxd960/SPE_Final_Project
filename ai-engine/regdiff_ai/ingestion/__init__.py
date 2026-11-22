"""Reading documents and splitting them into clauses (ING-1 to ING-5)."""

from regdiff_ai.ingestion.parser import ParsedClause, ParsedDocument, ParseError, parse_file, parse_text

__all__ = ["ParseError", "ParsedClause", "ParsedDocument", "parse_file", "parse_text"]
