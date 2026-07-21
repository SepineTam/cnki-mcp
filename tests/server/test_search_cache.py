#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/server/test_search_cache.py

"""Tests for the in-memory MCP search-result cache."""

from cnki_mcp.core.models import SearchResult
from cnki_mcp.server.search_cache import SearchResultCache


class Clock:
    """Controllable monotonic clock for cache tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _result(url: str) -> SearchResult:
    """Build a minimal cached search result."""
    return SearchResult(article_id=url, title=url, url=url)


def test_cache_returns_result_within_ten_minutes() -> None:
    """A cached URL remains available before the 600-second TTL."""
    clock = Clock()
    cache = SearchResultCache(clock=clock)
    result = _result("https://kns.cnki.net/article?v=1")
    cache.put([result])

    clock.now = 599.9

    assert cache.get(result.url or "") is result


def test_cache_expires_result_after_ten_minutes() -> None:
    """A cached URL is removed when its 600-second TTL expires."""
    clock = Clock()
    cache = SearchResultCache(clock=clock)
    result = _result("https://kns.cnki.net/article?v=1")
    cache.put([result])

    clock.now = 600.0

    assert cache.get(result.url or "") is None
    assert len(cache) == 0


def test_cache_normalizes_equivalent_urls() -> None:
    """Host casing, fragments, and query ordering do not create duplicates."""
    cache = SearchResultCache()
    result = _result("https://KNS.CNKI.NET/article?b=2&a=1#section")
    cache.put([result])

    assert cache.get("https://kns.cnki.net/article?a=1&b=2") is result


def test_cache_evicts_oldest_result_at_capacity() -> None:
    """The oldest entry is evicted before memory can grow without bound."""
    cache = SearchResultCache(max_entries=2)
    first = _result("https://kns.cnki.net/article?v=1")
    second = _result("https://kns.cnki.net/article?v=2")
    third = _result("https://kns.cnki.net/article?v=3")

    cache.put([first, second, third])

    assert cache.get(first.url or "") is None
    assert cache.get(second.url or "") is second
    assert cache.get(third.url or "") is third


def test_cache_uses_article_id_when_url_is_missing() -> None:
    """Dynamic article identifiers remain cacheable when url is absent."""
    cache = SearchResultCache()
    result = SearchResult(
        article_id="https://kns.cnki.net/article?v=1",
        title="T",
    )

    cache.put([result])

    assert cache.get(result.article_id) is result


def test_cache_clear_removes_every_result() -> None:
    """Server shutdown clears all cached records."""
    cache = SearchResultCache()
    cache.put([_result("https://kns.cnki.net/article?v=1")])

    cache.clear()

    assert len(cache) == 0
