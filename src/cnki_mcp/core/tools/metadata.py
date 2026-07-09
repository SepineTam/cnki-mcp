#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/tools/metadata.py

"""Atomic metadata retrieval operation for a single CNKI article."""

from urllib.parse import urlparse

from ..auth import ensure_login
from ..config import PAGE_LOAD_TIMEOUT_SECONDS
from ..exceptions import MetadataError, ParseError
from ..models import Article
from ..parsers.detail_parser import parse
from ..ratelimit import rate_limited
from ..runtime import Runtime

DETAIL_READY_SELECTOR = "h1, .wxTitle h1, #ChDivSummary, .abstract"


def build_detail_url(article_id: str) -> str:
    """Build a CNKI article detail URL.

    Args:
        article_id: Article identifier.

    Returns:
        Detail page URL containing the article identifier.
    """
    parsed = urlparse(article_id)
    if parsed.scheme in {"http", "https"} and parsed.netloc.endswith("cnki.net"):
        return article_id
    if article_id.startswith("/"):
        return f"https://kns.cnki.net{article_id}"
    return f"https://kns.cnki.net/kcms2/article/abstract?v={article_id}"


def _wait_for_detail(page: object) -> None:
    """Wait until the CNKI detail page has enough DOM to parse."""
    wait_for_selector = getattr(page, "wait_for_selector", None)
    if wait_for_selector is None:
        return
    try:
        wait_for_selector(
            DETAIL_READY_SELECTOR,
            state="attached",
            timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
        )
    except Exception:
        return


@rate_limited(profile=None)
def run(article_id: str, *, profile: str | None = None) -> Article:
    """Fetch and parse metadata for a CNKI article.

    Args:
        article_id: Article identifier.
        profile: Optional profile name; defaults to the current default.

    Returns:
        Parsed article metadata.

    Raises:
        MetadataError: When metadata retrieval or parsing fails.
    """
    try:
        ensure_login(profile=profile)
        with Runtime(profile=profile) as runtime:
            url = build_detail_url(article_id)
            page = runtime.get_page()
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
            )
            _wait_for_detail(page)
            return parse(page)
    except ParseError as exc:
        raise MetadataError(f"failed to parse article metadata: {exc}") from exc
    except Exception as exc:
        raise MetadataError(f"metadata retrieval failed: {exc}") from exc


__all__ = [
    "build_detail_url",
    "run",
]
