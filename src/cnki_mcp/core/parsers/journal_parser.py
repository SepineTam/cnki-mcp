#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/parsers/journal_parser.py

"""Parse CNKI journal navigation pages without making network requests."""

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from ..exceptions import ParseError
from ..models import JournalRecord, SearchResult

NAVI_BASE_URL = "https://navi.cnki.net/"
ISSN_PATTERN = re.compile(r"(?<!\d)(\d{4}-\d{3}[\dXx])(?!\d)")


def _journal_code_from_image(url: str | None) -> str | None:
    """Extract the stable journal code from a cover image URL."""
    if not url:
        return None
    filename = urlparse(url).path.rsplit("/", 1)[-1]
    code = filename.rsplit(".", 1)[0].strip()
    return code.upper() or None


def parse_search_results(page: Any) -> list[JournalRecord]:
    """Parse journal cards from a loaded navi search page."""
    cards = page.eval_on_selector_all(
        'a[href*="/knavi/detail"]',
        """(items) => items.map((item) => ({
            name: item.getAttribute("title") ||
                item.querySelector("h1")?.innerText.trim() ||
                item.innerText.trim(),
            url: item.href,
            image: item.querySelector("img")?.src || ""
        }))""",
    )
    records: list[JournalRecord] = []
    seen_urls: set[str] = set()
    for card in cards:
        name = str(card.get("name") or "").strip()
        url = str(card.get("url") or "").strip()
        if not name or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        records.append(
            JournalRecord(
                name=name,
                url=urljoin(NAVI_BASE_URL, url),
                code=_journal_code_from_image(card.get("image")),
            )
        )
    return records


def parse_journal_record(
    page: Any,
    *,
    url: str | None = None,
) -> JournalRecord:
    """Parse canonical journal identity from a loaded navi detail page."""
    values = page.evaluate(
        """() => ({
            name: document.querySelector("#shareChName")?.value || "",
            code: document.querySelector("#pykm")?.value || "",
            body: document.body?.innerText || ""
        })"""
    )
    name = str(values.get("name") or "").strip()
    code = str(values.get("code") or "").strip().upper() or None
    match = ISSN_PATTERN.search(str(values.get("body") or ""))
    if not name:
        raise ParseError("missing journal name on CNKI navigation detail page")
    return JournalRecord(
        name=name,
        url=url or page.url,
        issn=match.group(1).upper() if match else None,
        code=code,
    )


def parse_issue_html(
    page: Any,
    html: str,
    *,
    journal_name: str,
    year: int,
) -> tuple[list[SearchResult], int]:
    """Parse one HTML page of a navi issue catalog."""
    payload = page.evaluate(
        """(html) => {
            const doc = new DOMParser().parseFromString(html, "text/html");
            const total = Number(doc.querySelector("#articleCount")?.value || 0);
            const rows = Array.from(doc.querySelectorAll("dd.row")).map((row) => {
                const link = row.querySelector(
                    'a[href*="/kcms2/article/abstract"]'
                );
                return {
                    title: link?.innerText.trim() || "",
                    url: link?.href || "",
                    articleId: row.querySelector('[name="encrypt"]')?.id || "",
                    authors: row.querySelector(".author")?.getAttribute("title") || "",
                    pages: row.querySelector(".company")?.getAttribute("title") || ""
                };
            });
            return {total, rows};
        }""",
        html,
    )
    results: list[SearchResult] = []
    for row in payload["rows"]:
        title = str(row.get("title") or "").strip()
        article_id = str(row.get("articleId") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title or not article_id or not url:
            continue
        authors = [
            author.strip()
            for author in str(row.get("authors") or "").split(";")
            if author.strip()
        ]
        results.append(
            SearchResult(
                article_id=article_id,
                title=title,
                authors=authors,
                year=year,
                source=journal_name,
                url=urljoin("https://kns.cnki.net/", url),
            )
        )
    total_count = int(payload.get("total") or len(results))
    return results, total_count


__all__ = [
    "parse_issue_html",
    "parse_journal_record",
    "parse_search_results",
]
