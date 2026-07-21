#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/tools/journal.py

"""Resolve CNKI journals and retrieve one complete issue catalog."""

import re
import unicodedata
from typing import Any
from urllib.parse import urlencode

from ..auth import ensure_login
from ..config import PAGE_LOAD_TIMEOUT_SECONDS
from ..exceptions import (
    IssueNotAvailable,
    JournalLookupError,
    JournalNotFound,
)
from ..models import Article, JournalIssue, JournalRecord, SearchResult
from ..parsers import journal_parser
from ..runtime import Runtime
from . import metadata, professional_search

DETAIL_RETRY_COUNT = 2
ISSUE_PAGE_SIZE = 20
MAX_CATALOG_PAGES = 100
ISSN_PATTERN = re.compile(r"^\d{4}-\d{3}[\dX]$")
JOURNAL_SEARCH_URL = "https://navi.cnki.net/knavi/journals/search"


def _normalize_issn(issn: str | None) -> str | None:
    """Return a canonical ISSN with a hyphen."""
    if issn is None:
        return None
    compact = re.sub(r"[\s-]+", "", issn).upper()
    if len(compact) == 8:
        compact = f"{compact[:4]}-{compact[4:]}"
    if not ISSN_PATTERN.fullmatch(compact):
        raise JournalLookupError("ISSN must use the format 1234-567X")
    return compact


def _normalize_issue(vol: int | str) -> str:
    """Normalize the public vol argument used as the issue number."""
    cleaned = str(vol).strip()
    if not cleaned:
        raise JournalLookupError("vol must be a non-empty issue number")
    if cleaned.isdigit():
        number = int(cleaned)
        if number < 1:
            raise JournalLookupError("vol must be greater than zero")
        return str(number)
    return cleaned.casefold()


def _normalized_journal_name(value: str | None) -> str:
    """Normalize spaces and punctuation used by journal navigation."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        character
        for character in normalized
        if not character.isspace()
        and not unicodedata.category(character).startswith("P")
    )


def validate_request(
    *,
    year: int,
    vol: int | str,
    issn: str | None = None,
) -> tuple[str, str]:
    """Validate and normalize one issue-list request."""
    cleaned_issn = _normalize_issn(issn)
    if cleaned_issn is None:
        raise JournalLookupError("issn is required")
    if year < 1:
        raise JournalLookupError("year must be greater than zero")
    return cleaned_issn, _normalize_issue(vol)


def build_search_url(name: str) -> str:
    """Build the stable navi search URL for one journal name."""
    cleaned = _normalized_journal_name(name)
    if not cleaned:
        raise JournalLookupError("journal name is required")
    return f"{JOURNAL_SEARCH_URL}?{urlencode({'q': cleaned, 'field': 'TI'})}"


def _search_journal_cards(page: Any, name: str) -> list[JournalRecord]:
    """Load and parse all candidates returned on a navi search page."""
    page.goto(
        build_search_url(name),
        wait_until="domcontentloaded",
        timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
    )
    try:
        page.wait_for_selector(
            'a[href*="/knavi/detail"]',
            state="attached",
            timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
        )
    except Exception as exc:
        raise JournalNotFound(f"Journal not found: {name}") from exc
    records = journal_parser.parse_search_results(page)
    if not records:
        raise JournalNotFound(f"Journal not found: {name}")
    return records


def _load_journal_record(page: Any, candidate: JournalRecord) -> JournalRecord:
    """Load one fresh navi detail URL and parse its stable identity."""
    page.goto(
        candidate.url,
        wait_until="domcontentloaded",
        timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
    )
    try:
        page.wait_for_selector(
            "#pykm",
            state="attached",
            timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
        )
    except Exception as exc:
        raise JournalLookupError(
            f"Journal detail page did not load: {candidate.name}"
        ) from exc
    return journal_parser.parse_journal_record(page, url=candidate.url)


def resolve_journal_on_page(page: Any, name: str) -> JournalRecord:
    """Resolve a fresh detail URL and stable identity for an exact journal."""
    records = _search_journal_cards(page, name)

    expected = _normalized_journal_name(name)
    exact = next(
        (
            record
            for record in records
            if _normalized_journal_name(record.name) == expected
        ),
        None,
    )
    if exact is None:
        raise JournalNotFound(f"Journal not found: {name}")
    return _load_journal_record(page, exact)


def search_issn_on_page(page: Any, journal: str) -> dict[str, str]:
    """Return every navi search candidate that exposes an ISSN."""
    records = [
        _load_journal_record(page, candidate)
        for candidate in _search_journal_cards(page, journal)
    ]
    results = {
        record.name: record.issn
        for record in records
        if record.issn is not None
    }
    if not results:
        raise JournalLookupError(f"No ISSN found for journal search: {journal}")
    return results


def search_issn(
    journal: str,
    *,
    profile: str | None = None,
) -> dict[str, str]:
    """Resolve one journal name to its ISSN in a temporary runtime."""
    ensure_login(profile=profile)
    with Runtime(profile=profile) as runtime:
        return search_issn_on_page(runtime.get_page(), journal)


def _resolve_request_journal(
    page: Any,
    *,
    issn: str,
) -> JournalRecord:
    """Resolve the public ISSN to a fresh navi journal record."""
    expression = professional_search._build_clause("SN", issn)
    results = professional_search.run_expression_on_page(
        page,
        expression,
        sort_by="relevance",
        limit=20,
        max_pages=1,
    )
    source_names = list(
        dict.fromkeys(
            result.source.strip()
            for result in results
            if result.source and result.source.strip()
        )
    )
    for source_name in source_names:
        try:
            record = resolve_journal_on_page(page, source_name)
        except JournalNotFound:
            continue
        if record.issn == issn:
            return record
    raise JournalNotFound(f"Journal not found for ISSN: {issn}")


def _find_issue_token(
    page: Any,
    *,
    year: int,
    issue: str,
) -> str | None:
    """Read the current dynamic token for one year and issue."""
    page.wait_for_selector(
        "#YearIssueTree",
        state="attached",
        timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
    )
    if issue.isdigit():
        selector = f"#yq{year}{int(issue):02d}"
        locator = page.locator(selector)
        if locator.count():
            value = locator.first.get_attribute("value")
            return value.strip() if value else None

    nodes = page.eval_on_selector_all(
        f'[id^="yq{year}"]',
        """(items) => items.map((item) => ({
            text: item.innerText.trim(),
            value: item.getAttribute("value") || ""
        }))""",
    )
    expected = _normalize_issue(issue)
    for node in nodes:
        text = str(node.get("text") or "")
        number_match = re.search(r"\d+", text)
        actual = number_match.group() if number_match else text
        if _normalize_issue(actual) == expected:
            value = str(node.get("value") or "").strip()
            return value or None
    return None


def _fetch_issue_html(
    page: Any,
    record: JournalRecord,
    *,
    token: str,
    page_idx: int,
) -> str:
    """Fetch one issue catalog page inside the current browser session."""
    if not record.code:
        raise JournalLookupError(f"Journal code is unavailable: {record.name}")
    query = urlencode(
        {
            "yearIssue": token,
            "pageIdx": page_idx,
            "pcode": "CJFD,CCJD",
            "isEpublish": 0,
            "language": "CHS",
            "uniplatform": "NZKPT",
        }
    )
    url = f"https://navi.cnki.net/knavi/journals/{record.code}/papers?{query}"
    response = page.evaluate(
        """async (url) => {
            const response = await fetch(url, {
                method: "POST",
                credentials: "include"
            });
            return {
                ok: response.ok,
                status: response.status,
                text: await response.text()
            };
        }""",
        url,
    )
    if not response["ok"]:
        raise JournalLookupError(
            f"Journal catalog request failed with HTTP {response['status']}"
        )
    return str(response["text"])


def _collect_issue_catalog(
    page: Any,
    record: JournalRecord,
    *,
    token: str,
    year: int,
) -> list[SearchResult]:
    """Fetch and parse every catalog page for one journal issue."""
    results: list[SearchResult] = []
    seen_ids: set[str] = set()
    total_count: int | None = None
    for page_idx in range(MAX_CATALOG_PAGES):
        html = _fetch_issue_html(
            page,
            record,
            token=token,
            page_idx=page_idx,
        )
        page_results, parsed_total = journal_parser.parse_issue_html(
            page,
            html,
            journal_name=record.name,
            year=year,
        )
        if total_count is None:
            total_count = parsed_total
        new_results = [
            result for result in page_results if result.article_id not in seen_ids
        ]
        for result in new_results:
            seen_ids.add(result.article_id)
            results.append(result)
        if total_count == 0 or len(results) >= total_count:
            break
        if not new_results or len(page_results) < ISSUE_PAGE_SIZE:
            break
    return results


def _candidate_target(candidate: SearchResult) -> str:
    """Return the best detail target from a catalog row."""
    return candidate.url or candidate.article_id


def _load_article(page: Any, candidate: SearchResult) -> Article:
    """Load one detail page with a bounded retry for transient failures."""
    target = _candidate_target(candidate)
    last_error: Exception | None = None
    for _ in range(DETAIL_RETRY_COUNT):
        try:
            return metadata.run_on_page(page, target)
        except Exception as exc:
            last_error = exc
    raise JournalLookupError(
        f"failed to retrieve article metadata after {DETAIL_RETRY_COUNT} attempts: "
        f"{candidate.title} ({target}): {last_error}"
    ) from last_error


def _unavailable_message(
    *,
    issn: str,
    year: int,
    vol: int | str,
) -> str:
    """Build a stable English error for unpublished or missing issues."""
    return (
        f"Journal issue is unavailable: issn={issn!r}, "
        f"year={year}, vol={vol!r}"
    )


def run_on_page(
    page: Any,
    *,
    issn: str,
    year: int,
    vol: int | str,
) -> JournalIssue:
    """Retrieve complete metadata for one published issue through navi."""
    cleaned_issn, requested_issue = validate_request(
        issn=issn,
        year=year,
        vol=vol,
    )
    record = _resolve_request_journal(
        page,
        issn=cleaned_issn,
    )
    token = _find_issue_token(page, year=year, issue=requested_issue)
    if token is None:
        raise IssueNotAvailable(
            _unavailable_message(
                issn=cleaned_issn,
                year=year,
                vol=vol,
            )
        )
    candidates = _collect_issue_catalog(
        page,
        record,
        token=token,
        year=year,
    )
    article_candidates = [candidate for candidate in candidates if candidate.authors]
    articles = [_load_article(page, candidate) for candidate in article_candidates]
    if not articles:
        raise IssueNotAvailable(
            _unavailable_message(
                issn=cleaned_issn,
                year=year,
                vol=vol,
            )
        )

    first = articles[0]
    return JournalIssue(
        name=record.name,
        issn=record.issn,
        year=year,
        volume=first.volume,
        issue=first.issue or requested_issue,
        articles=articles,
    )


def run(
    *,
    issn: str,
    year: int,
    vol: int | str,
    profile: str | None = None,
) -> JournalIssue:
    """Retrieve one journal issue in a temporary browser runtime."""
    ensure_login(profile=profile)
    with Runtime(profile=profile) as runtime:
        return run_on_page(
            runtime.get_page(),
            issn=issn,
            year=year,
            vol=vol,
        )


__all__ = [
    "build_search_url",
    "resolve_journal_on_page",
    "run",
    "run_on_page",
    "search_issn",
    "search_issn_on_page",
    "validate_request",
]
