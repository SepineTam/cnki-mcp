#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/tools/search.py

"""Atomic search operation for CNKI."""

from urllib.parse import urlencode

from ..auth import ensure_login
from ..config import PAGE_LOAD_TIMEOUT_SECONDS
from ..exceptions import ParseError, SearchError
from ..models import SearchResult
from ..parsers.search_parser import parse
from ..ratelimit import rate_limited
from ..runtime import Runtime

CNKI_KNS_SEARCH_URL = "https://kns.cnki.net/kns8s/defaultresult/index"
DEFAULT_CROSSIDS = (
    "YSTT4HG0,LSTPFY1C,EMRPGLPA,JUP3MUPD,MPMFIG1A,WQ0UVIAA,"
    "BLZOG7CK,PWFIRAGL,NLBO1Z6R,NN3FJMUV"
)
DEFAULT_SEARCH_FIELD = "SU"
SECURITY_VERIFICATION_TEXT = "请完成安全验证"


def build_search_url(query: str, *, page: int = 1) -> str:
    """Build a CNKI search results URL.

    Args:
        query: Search query string.
        page: Page number (one-based).

    Returns:
        Encoded search URL.
    """
    params = {
        "crossids": DEFAULT_CROSSIDS,
        "korder": DEFAULT_SEARCH_FIELD,
        "kw": query,
    }
    if page > 1:
        params["page"] = str(page)
    return f"{CNKI_KNS_SEARCH_URL}?{urlencode(params)}"


def _wait_for_results(page: object) -> None:
    """Wait until the CNKI result page has rendered a searchable state."""
    wait_for_selector = getattr(page, "wait_for_selector", None)
    if wait_for_selector is None:
        return
    try:
        wait_for_selector(
            "#briefRequest, #gridTable, .result-table-list",
            state="attached",
            timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
        )
    except Exception:
        _raise_for_security_verification(page)


def _raise_for_security_verification(page: object) -> None:
    """Raise a clear error if CNKI asks for manual security verification."""
    try:
        title = page.title()
    except Exception:
        title = ""
    try:
        body = page.inner_text("body", timeout=3000)
    except Exception:
        body = ""
    if "安全验证" in title or SECURITY_VERIFICATION_TEXT in body:
        raise SearchError("CNKI requires manual security verification")


def _goto_search_page(page: object, query: str) -> None:
    """Open the CNKI KNS search page for a query."""
    page.goto(
        build_search_url(query),
        wait_until="domcontentloaded",
        timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
    )
    _wait_for_results(page)


def _turn_to_page(page: object, page_number: int) -> bool:
    """Move the rendered CNKI result page to another page number."""
    if page_number <= 1:
        return True
    try:
        clicked = page.evaluate(
            """(targetPage) => {
                const link = document.querySelector(
                    `.pages a[data-curpage="${targetPage}"], ` +
                    `#PageNext[data-curpage="${targetPage}"], ` +
                    `#Page_next[data-curpage="${targetPage}"], ` +
                    `#Page_next_top[data-curpage="${targetPage}"]`
                );
                if (!link) {
                    return false;
                }
                link.click();
                return true;
            }""",
            str(page_number),
        )
        if not clicked:
            return False
        page.wait_for_function(
            """(targetPage) => {
                const current = document.querySelector("#curPageHid");
                return current && current.value === targetPage;
            }""",
            str(page_number),
            timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
        )
        _wait_for_results(page)
        return True
    except Exception:
        return False


@rate_limited(profile=None)
def run(
    query: str,
    *,
    profile: str | None = None,
    limit: int = 10,
    max_pages: int = 1,
) -> list[SearchResult]:
    """Run a CNKI search and return parsed results.

    Args:
        query: Search query string.
        profile: Optional profile name; defaults to the current default.
        limit: Maximum number of results to return.
        max_pages: Maximum number of result pages to traverse.

    Returns:
        List of search results up to ``limit``.

    Raises:
        SearchError: When the search workflow fails.
    """
    try:
        ensure_login(profile=profile)
        with Runtime(profile=profile) as runtime:
            page = runtime.get_page()
            _goto_search_page(page, query)
            results: list[SearchResult] = []
            for page_number in range(1, max_pages + 1):
                if page_number > 1 and not _turn_to_page(page, page_number):
                    break
                results.extend(parse(page))
                if len(results) >= limit:
                    break
            return results[:limit]
    except ParseError as exc:
        raise SearchError(f"failed to parse search results: {exc}") from exc
    except SearchError:
        raise
    except Exception as exc:
        raise SearchError(f"search failed: {exc}") from exc


__all__ = [
    "build_search_url",
    "run",
]
