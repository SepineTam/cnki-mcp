#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/parsers/search_parser.py

"""Parse CNKI search result pages into SearchResult objects."""

import re
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from playwright.sync_api import ElementHandle, Page

from ..exceptions import ParseError
from ..models import SearchResult

RESULT_CONTAINER_SELECTOR = (
    "#gridTable .result-table-list tbody tr, "
    "#gridTable table tbody tr, "
    "#gridTable dl.result-detail-list dd, "
    ".result-list .result-item, "
    ".result-item"
)

FIELD_SELECTORS: dict[str, list[str]] = {
    "article_id": [
        "td.name a[href*='/kcms2/article/abstract']",
        "h6 a[href*='/kcms2/article/abstract']",
        ".article-id",
        "[data-article-id]",
        "input[name='filename']",
        "input[name='CookieName']",
    ],
    "title": [
        "td.name a[href*='/kcms2/article/abstract']",
        "td.name a.fz14",
        "h6 a[href*='/kcms2/article/abstract']",
        ".title",
        "a.title",
        "[data-title]",
    ],
    "authors": [
        "td.author a",
        ".author a",
        ".author",
        ".authors",
        "[data-author]",
    ],
    "year": ["td.date", ".year", "[data-year]", ".date"],
    "source": [
        "td.source a",
        "td.source",
        ".source a",
        ".source",
        "[data-source]",
        ".journal",
    ],
    "url": [
        "td.name a[href*='/kcms2/article/abstract']",
        "h6 a[href*='/kcms2/article/abstract']",
        ".title",
        "a.title",
        "[data-url]",
    ],
    "citation_count": [
        "td.quote",
        ".citation-count",
        ".cited",
        "[data-citation]",
        ".citations",
    ],
}


def _parse_citation_count(text: str | None) -> int | None:
    """Extract a numeric citation count from text."""
    if text is None:
        return None
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def _extract_article_id_from_url(url: str | None) -> str | None:
    """Try to extract an article id from a CNKI detail URL."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.netloc.endswith("cnki.net") and "/kcms2/article/abstract" in parsed.path:
        return url
    query = parse_qs(parsed.query)
    if "filename" in query:
        return query["filename"][0]
    path_parts = [part for part in parsed.path.split("/") if part]
    if path_parts:
        return path_parts[-1]
    return None


def _get_text(element: Optional["ElementHandle"]) -> str | None:
    """Return stripped text content of an element, or None."""
    if element is None:
        return None
    text = element.text_content()
    if text is None:
        return None
    return text.strip() or None


def _get_first_text(item: "ElementHandle", selectors: list[str]) -> str | None:
    """Try selectors in order and return stripped text of the first match."""
    for selector in selectors:
        element = item.query_selector(selector)
        text = _get_text(element)
        if text:
            return text
    return None


def _get_all_text(item: "ElementHandle", selectors: list[str]) -> list[str]:
    """Try selectors in order and return stripped text from all matches."""
    for selector in selectors:
        elements = item.query_selector_all(selector)
        if elements:
            texts = [_get_text(element) for element in elements]
            return [text for text in texts if text]
    return []


def _get_attr(
    item: "ElementHandle", selectors: list[str], attr: str
) -> str | None:
    """Try selectors in order and return an attribute of the first match."""
    for selector in selectors:
        element = item.query_selector(selector)
        if element is None:
            continue
        value = element.get_attribute(attr)
        if value:
            return value.strip()
    return None


def _get_base_url(item: "ElementHandle") -> str | None:
    """Return the page URL associated with an element if Playwright exposes it."""
    try:
        owner_frame = item.owner_frame()
        page = owner_frame.page if owner_frame is not None else None
        return page.url if page is not None else None
    except Exception:
        return None


def _normalize_url(url: str | None, base_url: str | None = None) -> str | None:
    """Normalize a possibly relative URL."""
    if not url:
        return None
    if base_url:
        return urljoin(base_url, url)
    return url


def _parse_result_item(item: Any, selectors: dict[str, list[str]]) -> SearchResult:
    """Parse a single search result item into a SearchResult.

    Args:
        item: Playwright element handle representing one search result.
        selectors: Field selector configuration.

    Returns:
        Parsed search result.

    Raises:
        ParseError: If the article id or title cannot be extracted.
    """
    title = _get_first_text(item, selectors["title"])
    if title is None:
        raise ParseError("missing required field: title")

    url = _normalize_url(_get_attr(item, selectors["url"], "href"), _get_base_url(item))

    article_ref = _normalize_url(
        _get_attr(item, selectors["article_id"], "href"),
        _get_base_url(item),
    )
    article_id = _extract_article_id_from_url(article_ref) if article_ref else None
    if article_id is None:
        article_id = _extract_article_id_from_url(url)
    if article_id is None:
        article_id = _get_attr(item, selectors["article_id"], "value")
    if article_id is None:
        article_id = _get_first_text(item, selectors["article_id"])

    if article_id is None:
        raise ParseError("missing required field: article_id")

    authors = _get_all_text(item, selectors["authors"])
    if len(authors) == 1 and ";" in authors[0]:
        authors = [author.strip() for author in authors[0].split(";") if author.strip()]

    year_text = _get_first_text(item, selectors["year"])
    year = _parse_citation_count(year_text)

    source = _get_first_text(item, selectors["source"])

    citation_text = _get_first_text(item, selectors["citation_count"])
    citation_count = _parse_citation_count(citation_text)

    return SearchResult(
        article_id=article_id,
        title=title,
        authors=authors,
        year=year,
        source=source,
        url=url,
        citation_count=citation_count,
    )


def parse(page: "Page") -> list[SearchResult]:
    """Parse a CNKI search result page.

    Args:
        page: Playwright page containing search results.

    Returns:
        List of parsed search results.
    """
    items = page.query_selector_all(RESULT_CONTAINER_SELECTOR)
    return [_parse_result_item(item, FIELD_SELECTORS) for item in items]


def parse_html(html: str, url: str | None = None) -> list[SearchResult]:
    """Parse CNKI search result HTML offline.

    Args:
        html: HTML string to parse.
        url: Optional base URL for the page.

    Returns:
        List of parsed search results.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(url or "about:blank")
            page.set_content(html)
            return parse(page)
        finally:
            browser.close()


def parse_total_count(page: "Page") -> int | None:
    """Extract the total result count from a search page if available.

    Args:
        page: Playwright page containing search results.

    Returns:
        Total result count or None if unavailable.
    """
    try:
        text = page.inner_text("body")
    except Exception:
        return None
    match = re.search(r"共找到\s*([\d,]+)\s*条结果", text)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


__all__ = [
    "RESULT_CONTAINER_SELECTOR",
    "FIELD_SELECTORS",
    "parse",
    "parse_html",
    "parse_total_count",
]
