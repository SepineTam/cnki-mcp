#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/parsers/export_parser.py

"""Parse CNKI citation exports without performing network requests."""

import re
from collections import defaultdict

from ..exceptions import ParseError
from ..models import Article

ENDNOTE_TAG_PATTERN = re.compile(r"^%([A-Z0-9])\s*(.*)$", re.I)
REFWORKS_TAG_PATTERN = re.compile(r"^([A-Z][A-Z0-9])\s+(.*)$", re.I)


def _parse_tagged_lines(
    text: str,
    pattern: re.Pattern[str],
) -> dict[str, list[str]]:
    """Parse tagged records and preserve repeated fields."""
    fields: dict[str, list[str]] = defaultdict(list)
    last_tag: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.strip().upper() in {"ER", "EF"}:
            break
        match = pattern.match(line)
        if match:
            tag = match.group(1).upper()
            value = match.group(2).strip()
            if value:
                fields[tag].append(value)
                last_tag = tag
            else:
                last_tag = None
            continue
        continuation = line.strip()
        if (
            raw_line[:1].isspace()
            and continuation
            and last_tag is not None
            and fields[last_tag]
        ):
            fields[last_tag][-1] = f"{fields[last_tag][-1]} {continuation}"
    return dict(fields)


def _first(fields: dict[str, list[str]], *tags: str) -> str | None:
    """Return the first non-empty value for the requested tags."""
    for tag in tags:
        values = fields.get(tag, [])
        if values:
            return values[0].strip() or None
    return None


def _all(fields: dict[str, list[str]], *tags: str) -> list[str]:
    """Return unique values for the requested tags in source order."""
    values = []
    seen = set()
    for tag in tags:
        for value in fields.get(tag, []):
            cleaned = value.strip(" ,，;；")
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                values.append(cleaned)
    return values


def _parse_year(value: str | None) -> int | None:
    """Extract a four-digit publication year."""
    if value is None:
        return None
    match = re.search(r"(?<!\d)(?:18|19|20|21)\d{2}(?!\d)", value)
    return int(match.group()) if match else None


def _parse_keywords(values: list[str]) -> list[str] | None:
    """Split and deduplicate exported keywords."""
    keywords = []
    seen = set()
    for value in values:
        for keyword in re.split(r"[;；]+", value):
            cleaned = keyword.strip(" ,，")
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                keywords.append(cleaned)
    return keywords or None


def _build_article(
    fields: dict[str, list[str]],
    *,
    endnote: bool,
) -> Article:
    """Map tagged citation fields to the public Article model."""
    if endnote:
        title = _first(fields, "T")
        authors = _all(fields, "A", "E")
        source = _first(fields, "J", "B")
        year_text = _first(fields, "D", "8")
        volume = _first(fields, "V")
        issue = _first(fields, "N")
        pages = _first(fields, "P")
        doi = _first(fields, "R")
        abstract = _first(fields, "X")
        keywords = _parse_keywords(_all(fields, "K"))
        url = _first(fields, "U")
    else:
        title = _first(fields, "T1", "TI")
        authors = _all(fields, "A1", "AU")
        source = _first(fields, "JF", "JO", "T2")
        year_text = _first(fields, "YR", "Y1", "PY")
        volume = _first(fields, "VO", "VL")
        issue = _first(fields, "IS")
        start_page = _first(fields, "SP")
        end_page = _first(fields, "OP", "EP")
        pages = start_page
        if start_page and end_page and start_page != end_page:
            pages = f"{start_page}-{end_page}"
        doi = _first(fields, "DO")
        abstract = _first(fields, "AB", "N2")
        keywords = _parse_keywords(_all(fields, "K1", "KW"))
        url = _first(fields, "UL", "UR")

    if not title:
        raise ParseError("citation export does not contain a title")

    return Article(
        article_id=doi or url or title,
        title=title,
        authors=authors,
        abstract=abstract,
        keywords=keywords,
        year=_parse_year(year_text),
        source=source,
        volume=volume,
        issue=issue,
        pages=pages,
        doi=doi,
        url=url,
    )


def parse(export_text: str) -> Article:
    """Parse one EndNote or RefWorks record into an Article."""
    text = export_text.strip()
    if not text:
        raise ParseError("citation export is empty")

    first_line = text.splitlines()[0].lstrip()
    if first_line.startswith("%"):
        fields = _parse_tagged_lines(text, ENDNOTE_TAG_PATTERN)
        return _build_article(fields, endnote=True)
    if REFWORKS_TAG_PATTERN.match(first_line):
        fields = _parse_tagged_lines(text, REFWORKS_TAG_PATTERN)
        return _build_article(fields, endnote=False)
    raise ParseError("unsupported citation export format")


__all__ = ["parse"]
