#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/parsers/detail_parser.py

"""Parse CNKI article detail pages into Article objects."""

import re

from playwright.sync_api import Error, Page, sync_playwright

from ..exceptions import ParseError
from ..models import Article

SELECTORS: dict[str, list[str]] = {
    "title": [
        ".wxTitle h1",
        ".brief h1",
        ".doc-top h1",
        ".titbox h1",
        ".title",
        "h1.title",
        "h1",
        "div.title",
        "span.title",
        ".c_title",
        "#Title",
    ],
    "authors": [
        ".authors a",
        ".author a",
        ".wxBaseinfo .author a",
        ".author",
        "a.author",
        ".author_list li",
        ".author-item",
        ".c_author",
    ],
    "institution": [
        ".orgn",
        ".orgn a",
        ".institutions a",
        ".institution",
        ".org",
        ".affiliation",
        ".c_org",
    ],
    "abstract": [
        "#ChDivSummary",
        "#EnChDivSummary",
        ".abstract-text",
        ".abstract span",
        ".abstract",
        "div.abstract",
        "p.abstract",
        ".c_abstract",
    ],
    "keywords": [
        ".keywords a",
        ".keyword a",
        "#catalog_KEYWORD a",
        ".keyword",
        "a.keyword",
        ".keyword_list li",
        ".keyword-item",
        ".c_keyword",
    ],
    "year": [
        ".sourinfo",
        ".source-info",
        ".year",
        ".pub-date",
        ".publishdate",
        ".c_year",
    ],
    "source": [
        ".sourinfo a",
        ".source-info a",
        ".top-tip a",
        ".source",
        ".journal",
        ".c_source",
    ],
    "doi": [
        ".doi",
        ".c_doi",
    ],
    "download_url": [
        ".download_url",
        ".download",
        "a.download",
        ".download a",
        ".c_download",
    ],
}

LABEL_ALIASES: dict[str, list[str]] = {
    "institution": ["机构", "作者单位", "单位"],
    "abstract": ["摘要", "Abstract"],
    "keywords": ["关键词", "Key words", "Keywords"],
    "source": ["来源", "刊名", "Source"],
    "doi": ["DOI"],
}


def _parse_text(page: Page, selectors: list[str]) -> str | None:
    """Return the first non-empty text matching any selector."""
    for selector in selectors:
        try:
            element = page.query_selector(selector)
            if element is None:
                continue
            text = element.inner_text().strip()
            if text:
                return text
        except Error:
            continue
    return None


def _parse_list(page: Page, selectors: list[str]) -> list[str]:
    """Return the first matching list of non-empty texts."""
    for selector in selectors:
        try:
            elements = page.query_selector_all(selector)
            texts = [element.inner_text().strip() for element in elements]
            texts = [text for text in texts if text]
            if texts:
                return texts
        except Error:
            continue
    return []


def _dedupe(values: list[str]) -> list[str]:
    """Return values without duplicates while preserving order."""
    result = []
    seen = set()
    for value in values:
        cleaned = re.sub(r"\s+", " ", value).strip(" ;；,，")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _split_people(text: str | None) -> list[str]:
    """Split a human-name field into a list."""
    if not text:
        return []
    text = re.sub(r"^(作者|Authors?)\s*[：:]\s*", "", text, flags=re.I)
    return _dedupe(re.split(r"[;；,，\s]+", text))


def _clean_author_name(text: str) -> str:
    """Normalize author text from KNS detail pages."""
    return re.sub(r"[\d\s,，;；*]+$", "", text).strip()


def _looks_like_institution(text: str) -> bool:
    """Return whether a text fragment is likely an institution."""
    cleaned = text.strip()
    if re.match(r"^\d+[.．、]\s*", cleaned):
        return True
    if len(cleaned) >= 12 and re.search(
        r"大学|学院|研究所|实验室|中心|医院|公司|部门|学部|图书馆",
        cleaned,
    ):
        return True
    return False


def _split_authors_and_institutions(values: list[str]) -> tuple[list[str], list[str]]:
    """Separate author names from institution fragments."""
    authors = []
    institutions = []
    for value in values:
        if _looks_like_institution(value):
            institutions.append(re.sub(r"^\d+[.．、]\s*", "", value).strip())
            continue
        author = _clean_author_name(value)
        if author:
            authors.append(author)
    return _dedupe(authors), _dedupe(institutions)


def _strip_label(text: str) -> str:
    """Remove a leading Chinese or English metadata label."""
    return re.sub(r"^[\w\s\u4e00-\u9fff]+[：:]\s*", "", text).strip()


def _parse_body_text(page: Page) -> str:
    """Return visible body text, or an empty string if unavailable."""
    try:
        return page.inner_text("body")
    except Error:
        return ""


def _parse_labeled_text(page: Page, field: str) -> str | None:
    """Extract metadata from visible text by common labels."""
    body = _parse_body_text(page)
    if not body:
        return None
    labels = LABEL_ALIASES.get(field, [])
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[：:]\s*(.+?)(?=\n\S{{1,12}}\s*[：:]|\Z)"
        match = re.search(pattern, body, flags=re.S | re.I)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip()
            if value:
                return value
    return None


def _parse_keywords(page: Page) -> list[str]:
    """Parse keyword lists from elements or labeled body text."""
    keywords = _parse_list(page, SELECTORS["keywords"])
    if not keywords:
        text = _parse_labeled_text(page, "keywords")
        if text:
            keywords = re.split(r"[;；,，]\s*", text)
    return _dedupe([_strip_label(keyword) for keyword in keywords])


def _parse_year(text: str | None) -> int | None:
    """Extract a four-digit year from text."""
    if text is None:
        return None
    match = re.search(r"\d{4}", text)
    return int(match.group()) if match else None


def _extract_article_id(page: Page, url: str | None = None) -> str | None:
    """Extract the article identifier from the page URL or hidden inputs."""
    target_url = url or page.url
    if target_url and target_url not in ("about:blank",):
        if "/kcms2/article/abstract" in target_url:
            return target_url
        match = re.search(r"[?&]filename=([^&#]+)", target_url)
        if match:
            return match.group(1)
        match = re.search(r"/article/([^/?#]+)", target_url)
        if match:
            return match.group(1)

    try:
        filename_input = page.query_selector('input[name="filename"]')
        if filename_input is not None:
            value = filename_input.get_attribute("value")
            if value:
                return value.strip()
    except Error:
        pass

    return None


def parse(page: Page, *, url: str | None = None) -> Article:
    """Parse a CNKI article detail page.

    Args:
        page: Playwright page containing article details.
        url: Optional URL to use when the page location is not set.

    Returns:
        Parsed article metadata.

    Raises:
        ParseError: When required fields cannot be extracted.
    """
    title = _parse_text(page, SELECTORS["title"])
    if not title:
        raise ParseError("could not extract title from detail page")

    article_id = _extract_article_id(page, url=url) or ""
    raw_authors = _dedupe(_parse_list(page, SELECTORS["authors"]))
    authors, author_institutions = _split_authors_and_institutions(raw_authors)
    if len(authors) == 1:
        authors = _split_people(authors[0]) or authors
    institution = _parse_text(page, SELECTORS["institution"])
    if institution:
        institution = _strip_label(institution)
    else:
        institution = _parse_labeled_text(page, "institution")
    if not institution and author_institutions:
        institution = "; ".join(author_institutions)
    abstract = _parse_text(page, SELECTORS["abstract"])
    if abstract:
        abstract = _strip_label(abstract)
    else:
        abstract = _parse_labeled_text(page, "abstract")
    keywords = _parse_keywords(page)
    year_text = _parse_text(page, SELECTORS["year"])
    year = _parse_year(year_text)
    source = _parse_text(page, SELECTORS["source"])
    if source:
        source = _strip_label(source).strip(" .。")
    else:
        source = _parse_labeled_text(page, "source")
    doi = _parse_text(page, SELECTORS["doi"])
    if doi:
        doi = _strip_label(doi)
    else:
        doi = _parse_labeled_text(page, "doi")

    page_url = url or page.url
    if page_url in ("about:blank",):
        page_url = None

    return Article(
        article_id=article_id,
        title=title,
        authors=authors,
        institution=institution,
        abstract=abstract,
        keywords=keywords or None,
        year=year,
        source=source,
        doi=doi,
        url=page_url,
        download_url=None,
    )


def parse_html(html: str, url: str | None = None) -> Article:
    """Parse CNKI detail HTML offline.

    Args:
        html: HTML string to parse.
        url: Optional base URL for the page.

    Returns:
        Parsed article metadata.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.set_content(html)
            return parse(page, url=url)
        finally:
            browser.close()


__all__ = [
    "SELECTORS",
    "parse",
    "parse_html",
]
