#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/server/test_tool_registry.py

"""Tests for the transport-independent MCP tool service."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest

from cnki_mcp.core.exceptions import LoginRequired
from cnki_mcp.core.models import Article, AuthState, SearchResult
from cnki_mcp.server.search_cache import SearchResultCache
from cnki_mcp.server.tool_registry import McpToolService


class FakeWorker:
    """Return queued browser results without creating Playwright objects."""

    def __init__(self, responses: list[Any]) -> None:
        """Initialize queued operation responses."""
        self.responses = list(responses)
        self.operations: list[Callable[[Any], Any]] = []
        self.started_profiles: list[str | None] = []
        self.close_count = 0
        self.current_profile: str | None = None

    def start(self, profile: str | None = None) -> object:
        """Record browser startup."""
        self.started_profiles.append(profile)
        self.current_profile = profile
        return object()

    def call(self, operation: Callable[[Any], Any]) -> Any:
        """Record an operation and return its queued result."""
        self.operations.append(operation)
        return self.responses.pop(0)

    def close(self) -> None:
        """Record browser shutdown."""
        self.close_count += 1

    def refresh_browser(self) -> dict[str, Any]:
        """Return the unimplemented recovery result."""
        return {"success": False, "error": "not implemented"}

    @property
    def is_running(self) -> bool:
        """Return whether a profile has been started."""
        return self.current_profile is not None


class ExecutingWorker(FakeWorker):
    """Execute submitted operations against a harmless page sentinel."""

    def __init__(self) -> None:
        """Initialize without queued responses."""
        super().__init__([])
        self.page = object()

    def call(self, operation: Callable[[Any], Any]) -> Any:
        """Execute an operation immediately."""
        self.operations.append(operation)
        return operation(self.page)


def _search_result() -> SearchResult:
    """Build a representative search result with a reusable detail URL."""
    return SearchResult(
        article_id="article-1",
        title="无心插柳",
        authors=["袁晓燕", "翁士汉"],
        date="2024-01-01",
        source="世界经济文汇",
        url="https://kns.cnki.net/kcms2/article/abstract?v=article-1",
    )


@patch("cnki_mcp.server.tool_registry.auth.list_profiles", return_value=[])
def test_network_start_requires_an_initialized_profile(_: Any) -> None:
    """Network MCP startup directs first-time users to the init command."""
    service = McpToolService(worker=FakeWorker([]), cache=SearchResultCache())

    with pytest.raises(LoginRequired, match="cnki-mcp init"):
        service.start_network()


def test_easy_search_returns_url_and_caches_full_result() -> None:
    """Compact search records include a URL reusable by the info tool."""
    search_result = _search_result()
    worker = FakeWorker([[search_result]])
    cache = SearchResultCache()
    service = McpToolService(worker=worker, cache=cache)

    results = service.easy_search("无心插柳", sort_by="date", limit=5)

    assert results == [
        {
            "title": "无心插柳",
            "authors": ["袁晓燕", "翁士汉"],
            "journal": "世界经济文汇",
            "date": "2024-01-01",
            "url": search_result.url,
        }
    ]
    assert cache.get(search_result.url or "") is search_result


def test_advanced_search_returns_url_and_caches_full_result() -> None:
    """Structured professional search has the same compact result shape."""
    search_result = _search_result()
    worker = FakeWorker([[search_result]])
    cache = SearchResultCache()
    service = McpToolService(worker=worker, cache=cache)

    results = service.advanced_search(
        title="无心插柳",
        author="袁晓燕",
        journal="世界经济文汇",
        limit=5,
    )

    assert results[0]["url"] == search_result.url
    assert cache.get(search_result.url or "") is search_result


@patch("cnki_mcp.server.tool_registry.basic_search.run_on_page")
def test_easy_search_executes_on_worker_page(mock_search: Any) -> None:
    """Easy search reuses the page owned by the persistent browser worker."""
    worker = ExecutingWorker()
    mock_search.return_value = [_search_result()]
    service = McpToolService(worker=worker, cache=SearchResultCache())

    service.easy_search("无心插柳", limit=5, sort_by="date")

    mock_search.assert_called_once_with(
        worker.page,
        "无心插柳",
        limit=5,
        max_pages=1,
        sort_by="date",
    )


@patch("cnki_mcp.server.tool_registry.professional_search.run_expression_on_page")
def test_advanced_search_executes_professional_expression(
    mock_search: Any,
) -> None:
    """Structured fields are converted before the worker runs the search."""
    worker = ExecutingWorker()
    mock_search.return_value = [_search_result()]
    service = McpToolService(worker=worker, cache=SearchResultCache())

    service.advanced_search(
        title="无心插柳",
        author="袁晓燕",
        journal="世界经济文汇",
    )

    _, expression = mock_search.call_args.args
    assert expression == (
        "TI='无心插柳' and AU='袁晓燕' and LY='世界经济文汇'"
    )


def test_get_info_from_url_returns_one_metadata_dict() -> None:
    """A search result URL resolves to one detailed metadata dictionary."""
    article = Article(
        article_id="article-1",
        title="无心插柳",
        abstract="摘要",
        url="https://kns.cnki.net/kcms2/article/abstract?v=article-1",
    )
    worker = FakeWorker([article])
    service = McpToolService(worker=worker, cache=SearchResultCache())

    result = service.get_info_from_url(article.url or "")

    assert isinstance(result, dict)
    assert result["title"] == "无心插柳"
    assert result["abstract"] == "摘要"


def test_get_info_by_detail_always_returns_a_list() -> None:
    """Detailed lookup keeps a list shape even for one unique match."""
    search_result = _search_result()
    article = Article(
        article_id="article-1",
        title="无心插柳",
        authors=["袁晓燕", "翁士汉"],
        source="世界经济文汇",
    )
    worker = FakeWorker([[search_result], article])
    service = McpToolService(worker=worker, cache=SearchResultCache())

    results = service.get_info_by_detail(
        title="无心插柳",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        journal="世界经济文汇",
    )

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["title"] == "无心插柳"


def test_get_info_by_detail_returns_empty_list_for_no_matches() -> None:
    """A professional search with no candidates returns an empty list."""
    worker = FakeWorker([[]])
    service = McpToolService(worker=worker, cache=SearchResultCache())

    results = service.get_info_by_detail(title="不存在的文章")

    assert results == []


@patch("cnki_mcp.server.tool_registry.metadata.run_on_page")
@patch("cnki_mcp.server.tool_registry.professional_search.run_expression_on_page")
def test_get_info_by_detail_preserves_other_results_on_one_failure(
    mock_search: Any,
    mock_metadata: Any,
) -> None:
    """One broken detail page does not discard other parsed articles."""
    first = _search_result()
    second = SearchResult(
        article_id="article-2",
        title="另一篇文章",
        url="https://kns.cnki.net/kcms2/article/abstract?v=article-2",
    )
    mock_search.return_value = [first, second]
    mock_metadata.side_effect = [
        Article(article_id="article-1", title="无心插柳"),
        RuntimeError("detail unavailable"),
    ]
    service = McpToolService(
        worker=ExecutingWorker(),
        cache=SearchResultCache(),
    )

    results = service.get_info_by_detail(title="文章")

    assert results[0]["title"] == "无心插柳"
    assert results[1] == {
        "success": False,
        "error": "detail unavailable",
        "title": "另一篇文章",
        "url": second.url,
    }


@patch("cnki_mcp.server.tool_registry.auth.require_profile", return_value="default")
@patch("cnki_mcp.server.tool_registry.auth.ensure_login")
def test_service_network_start_and_close_follow_worker_lifetime(
    mock_ensure_login: Any,
    mock_require_profile: Any,
) -> None:
    """The service delegates process-level browser ownership to its worker."""
    worker = FakeWorker([])
    cache = SearchResultCache()
    cache.put([_search_result()])
    service = McpToolService(worker=worker, cache=cache)

    service.start_network()
    service.close()

    mock_require_profile.assert_called_once_with()
    mock_ensure_login.assert_called_once_with(profile="default")
    assert worker.started_profiles == ["default"]
    assert worker.close_count == 1
    assert len(cache) == 0


@patch("cnki_mcp.server.tool_registry.auth.require_profile", return_value="school")
@patch("cnki_mcp.server.tool_registry.auth.ensure_login")
def test_stdio_login_starts_selected_profile(
    mock_ensure_login: Any,
    mock_require_profile: Any,
) -> None:
    """stdio login opens the persistent browser for the resolved profile."""
    mock_ensure_login.return_value = AuthState(
        is_logged_in=True,
        profile="school",
    )
    worker = FakeWorker([])
    service = McpToolService(worker=worker, cache=SearchResultCache())

    result = service.login("school")

    mock_require_profile.assert_called_once_with("school")
    mock_ensure_login.assert_called_once_with(profile="school")
    assert worker.started_profiles == ["school"]
    assert result == {"success": True, "profile": "school"}


@patch("cnki_mcp.server.tool_registry.auth.require_profile", return_value="school")
@patch("cnki_mcp.server.tool_registry.auth.ensure_login")
def test_stdio_login_is_idempotent_for_active_profile(
    mock_ensure_login: Any,
    mock_require_profile: Any,
) -> None:
    """Repeated login does not open the same persistent profile twice."""
    worker = FakeWorker([])
    worker.current_profile = "school"
    service = McpToolService(worker=worker, cache=SearchResultCache())

    result = service.login("school")

    mock_require_profile.assert_called_once_with("school")
    mock_ensure_login.assert_not_called()
    assert worker.started_profiles == []
    assert result == {"success": True, "profile": "school"}


@patch("cnki_mcp.server.tool_registry.auth.logout")
def test_stdio_logout_only_closes_browser(mock_delete_login: Any) -> None:
    """stdio logout preserves cookies and other persisted login state."""
    worker = FakeWorker([])
    worker.current_profile = "school"
    service = McpToolService(worker=worker, cache=SearchResultCache())

    result = service.logout()

    assert worker.close_count == 1
    mock_delete_login.assert_not_called()
    assert result == {"success": True, "profile": "school"}


@patch("cnki_mcp.server.tool_registry.auth.list_profiles")
@patch("cnki_mcp.server.tool_registry.auth.get_default_profile")
def test_profile_resource_exposes_names_only(
    mock_default_profile: Any,
    mock_list_profiles: Any,
) -> None:
    """Profile discovery returns no paths, cookies, or storage state."""
    mock_default_profile.return_value = "school"
    mock_list_profiles.return_value = ["profile1", "school"]
    service = McpToolService(worker=FakeWorker([]), cache=SearchResultCache())

    assert service.list_profiles() == {
        "default_profile": "school",
        "profiles": ["profile1", "school"],
    }


def test_refresh_browser_remains_an_internal_stub() -> None:
    """The service may retain recovery plumbing without publishing a tool."""
    worker = FakeWorker([])
    service = McpToolService(worker=worker, cache=SearchResultCache())

    assert service.refresh_browser() == {
        "success": False,
        "error": "not implemented",
    }
