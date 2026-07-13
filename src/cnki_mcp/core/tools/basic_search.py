#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/tools/basic_search.py

"""Atomic one-box search operation for CNKI."""

from collections.abc import Iterable
from urllib.parse import urlencode

from ..auth import ensure_login
from ..config import PAGE_LOAD_TIMEOUT_SECONDS
from ..exceptions import ParseError, SearchError
from ..models import SearchFilters, SearchResult
from ..parsers.search_parser import parse
from ..ratelimit import rate_limited
from ..runtime import Runtime
from . import professional_search, search

CNKI_ONE_BOX_SEARCH_URL = "https://kns.cnki.net/kns8s/defaultresult/index"
DEFAULT_CROSSIDS = (
    "YSTT4HG0,LSTPFY1C,EMRPGLPA,JUP3MUPD,MPMFIG1A,WQ0UVIAA,"
    "BLZOG7CK,PWFIRAGL,NLBO1Z6R,NN3FJMUV"
)


def build_search_url(query: str) -> str:
    """Build the CNKI one-box subject-search URL."""
    params = {
        "crossids": DEFAULT_CROSSIDS,
        "korder": "SU",
        "kw": query,
    }
    return f"{CNKI_ONE_BOX_SEARCH_URL}?{urlencode(params)}"


def _validate_options(
    *,
    limit: int,
    max_pages: int,
    institution: str | None,
) -> None:
    """Validate options that differ between one-box and professional search."""
    if limit < 1:
        raise SearchError("limit must be greater than zero")
    if max_pages < 1:
        raise SearchError("max_pages must be greater than zero")
    if institution:
        raise SearchError(
            "institution filtering requires --advanced professional search"
        )


def _contains(value: str | None, expected: str | None) -> bool:
    """Match a normalized optional text filter."""
    if expected is None:
        return True
    if value is None:
        return False
    return expected.casefold() in value.casefold()


def _filter_results(
    results: list[SearchResult],
    *,
    year_from: int | None = None,
    year_to: int | None = None,
    journal: str | None = None,
    author: str | None = None,
) -> list[SearchResult]:
    """Apply filters available in parsed one-box result rows."""
    start_year = year_from if year_from is not None else year_to
    end_year = year_to if year_to is not None else year_from
    if start_year is not None and end_year is not None and end_year < start_year:
        raise SearchError("year_to must be greater than or equal to year_from")

    filtered: list[SearchResult] = []
    for result in results:
        if start_year is not None:
            if result.year is None or not start_year <= result.year <= end_year:
                continue
        if not _contains(result.source, journal):
            continue
        if author and not any(_contains(value, author) for value in result.authors):
            continue
        filtered.append(result)
    return filtered


def _search_page(
    page: object,
    query: str,
    *,
    filter_payload: dict[str, object],
    sort_by: str | None,
    limit: int,
    max_pages: int,
) -> list[SearchResult]:
    """Load, filter, sort, and parse one-box result pages."""
    page.goto(
        build_search_url(query),
        wait_until="domcontentloaded",
        timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
    )
    professional_search._wait_for_results_or_empty(page)
    if professional_search._is_empty_result_page(page):
        return []
    professional_search._apply_result_filters(page, filter_payload)
    professional_search._apply_sort(page, sort_by)

    results: list[SearchResult] = []
    for page_number in range(1, max_pages + 1):
        if page_number > 1 and not professional_search._turn_to_page(
            page, page_number
        ):
            break
        results.extend(parse(page))
        if len(results) >= limit:
            break
    return results


@rate_limited(profile=None)
def run(
    query: str,
    *,
    profile: str | None = None,
    limit: int = 10,
    max_pages: int = 1,
    filters: SearchFilters | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    journal: str | None = None,
    document_type: str | None = None,
    source_types: Iterable[str] | str | None = None,
    author: str | None = None,
    institution: str | None = None,
    sort_by: str | None = None,
) -> list[SearchResult]:
    """Run a CNKI one-box search and return compact result records."""
    query = " ".join(query.split())
    if not query:
        raise SearchError("one-box search query is required")
    search_filters = search._normalize_filters(
        filters,
        year_from=year_from,
        year_to=year_to,
        journal=journal,
        document_type=document_type,
        source_types=source_types,
        author=author,
        institution=institution,
    )
    _validate_options(
        limit=limit,
        max_pages=max_pages,
        institution=search_filters.institution,
    )
    filter_payload = search._build_filter_payload(search_filters)

    try:
        ensure_login(profile=profile)
        with Runtime(profile=profile) as runtime:
            page = runtime.get_page()
            results = _search_page(
                page,
                query,
                filter_payload=filter_payload,
                sort_by=sort_by,
                limit=limit,
                max_pages=max_pages,
            )
        return _filter_results(
            results,
            year_from=search_filters.year_from,
            year_to=search_filters.year_to,
            journal=search_filters.journal,
            author=search_filters.author,
        )[:limit]
    except ParseError as exc:
        raise SearchError(f"failed to parse one-box search results: {exc}") from exc
    except SearchError:
        raise
    except Exception as exc:
        professional_search._raise_for_security_verification(locals().get("page"))
        raise SearchError(f"one-box search failed: {exc}") from exc


__all__ = ["build_search_url", "run"]
