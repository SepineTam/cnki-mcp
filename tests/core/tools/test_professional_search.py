#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/tools/test_professional_search.py

"""Tests for core/tools/professional_search.py."""

from unittest.mock import MagicMock, patch

import pytest

from cnki_mcp.core.exceptions import ParseError, SearchError
from cnki_mcp.core.models import SearchResult
from cnki_mcp.core.retrieval.models import CnkiQuery
from cnki_mcp.core.tools import professional_search


def test_build_expression_uses_cnki_professional_fields() -> None:
    """Known metadata becomes one precise CNKI professional expression."""
    query = CnkiQuery(
        title="无心插柳——世界杯“爆冷获胜”的贸易创造",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
    )

    assert professional_search.build_expression(query) == (
        "TI='无心插柳——世界杯“爆冷获胜”的贸易创造' "
        "and LY='世界经济文汇' and AU='袁晓燕' and AU='翁士汉'"
    )


def test_build_expressions_orders_wide_to_strict_fallbacks() -> None:
    """Fallback expressions narrow only after a broad title search."""
    query = CnkiQuery(
        title="无心插柳",
        authors=["袁晓燕", "翁士汉"],
        source="世界经济文汇",
    )

    assert professional_search.build_expressions(query) == [
        "TI='无心插柳'",
        "TI='无心插柳' and LY='世界经济文汇'",
        "TI='无心插柳' and AU='袁晓燕' and AU='翁士汉'",
        (
            "TI='无心插柳' and LY='世界经济文汇' "
            "and AU='袁晓燕' and AU='翁士汉'"
        ),
    ]


def test_build_expression_uses_alternate_quote_for_apostrophes() -> None:
    """An apostrophe stays literal by switching to double-quote delimiters."""
    query = CnkiQuery(
        title="O'Reilly research",
        authors=["D'Angelo"],
    )

    expression = professional_search.build_expression(query)

    assert expression == 'TI="O\'Reilly research" and AU="D\'Angelo"'


def test_build_expression_rejects_ambiguous_quote_content() -> None:
    """Mixed ASCII quote delimiters cannot inject expression operators."""
    query = CnkiQuery(title='x\' or SU="all"')

    with pytest.raises(SearchError, match="both quote types"):
        professional_search.build_expression(query)


def test_build_expression_omits_empty_optional_values() -> None:
    """Blank optional values do not add empty clauses."""
    query = CnkiQuery(title="  经济学研究  ", authors=[" "], source=" ")

    assert professional_search.build_expression(query) == "TI='经济学研究'"


def test_build_expression_quotes_cnki_operator_characters() -> None:
    """Operator-like characters stay inside one quoted literal term."""
    query = CnkiQuery(title="A+B*(C)/D%=E\n研究")

    assert professional_search.build_expression(query) == (
        "TI='A+B*(C)/D%=E 研究'"
    )


def test_build_expression_requires_title() -> None:
    """A blank title cannot identify a work reliably."""
    with pytest.raises(SearchError, match="title"):
        professional_search.build_expression(CnkiQuery(title=" "))


def test_year_validation_falls_back_to_parsed_results() -> None:
    """Year matching remains enforceable when page controls are unavailable."""
    results = [
        SearchResult(article_id="wrong", title="T", year=2023),
        SearchResult(article_id="right", title="T", year=2024),
    ]

    assert professional_search._filter_by_year(results, 2024) == [results[1]]
    assert "professional-search year range unavailable" not in (
        professional_search.SUBMIT_PROFESSIONAL_SEARCH_SCRIPT
    )


def test_sort_by_uses_verified_cnki_sort_codes() -> None:
    """Public sort names map only to verified professional-page controls."""
    assert professional_search._normalize_sort_by("relevance") == "FFD"
    assert professional_search._normalize_sort_by("date") == "PT"
    assert professional_search._normalize_sort_by("citation") == "CF"
    assert professional_search._normalize_sort_by("comprehensive") == "ZH"

    with pytest.raises(SearchError, match="unsupported sort_by"):
        professional_search._normalize_sort_by("downloads")


def test_apply_sort_clicks_professional_result_control() -> None:
    """Sorting uses the verified data-sort control on professional results."""
    page = MagicMock()
    page.evaluate.return_value = {"applied": True}

    professional_search._apply_sort(page, "citation")

    assert page.evaluate.call_args.args[1] == "CF"
    page.wait_for_timeout.assert_called_once_with(3000)


def test_submit_accepts_explicit_empty_result_page() -> None:
    """A valid zero-match search returns normally instead of timing out."""
    page = MagicMock()
    page.evaluate.return_value = {"submitted": True, "yearApplied": False}
    page.wait_for_selector.side_effect = [None, TimeoutError("no result table")]
    page.inner_text.return_value = "共找到 0 条结果"

    assert professional_search._submit(page, "TI='不存在的文章'") is False


@patch("cnki_mcp.core.tools.professional_search._submit")
def test_search_page_returns_empty_before_filters_and_sort(
    mock_submit: MagicMock,
) -> None:
    """Filters and sorting are skipped when the professional search is empty."""
    page = MagicMock()
    page.inner_text.return_value = "未检索到相关文献"
    mock_submit.return_value = False

    assert professional_search._search_page(
        page,
        "TI='不存在的文章'",
        filter_payload={"documentType": "学术期刊"},
        sort_by="date",
    ) == []

    assert page.evaluate.call_count == 0


@patch("cnki_mcp.core.tools.professional_search._turn_to_page")
@patch("cnki_mcp.core.tools.professional_search._submit")
@patch("cnki_mcp.core.tools.professional_search.parse")
def test_missing_year_controls_collects_all_requested_pages_before_filtering(
    mock_parse: MagicMock,
    mock_submit: MagicMock,
    mock_turn_to_page: MagicMock,
) -> None:
    """Local year validation is not limited before all pages are collected."""
    mock_submit.return_value = False
    mock_turn_to_page.return_value = True
    wrong = SearchResult(article_id="wrong", title="T", year=2023)
    right = SearchResult(article_id="right", title="T", year=2024)
    mock_parse.side_effect = [[wrong], [right]]

    results = professional_search._search_page(
        MagicMock(),
        "TI='T'",
        year_from=2024,
        year_to=2024,
        limit=1,
        max_pages=2,
    )

    assert results == [wrong, right]
    assert professional_search._filter_by_year(results, 2024) == [right]
    assert mock_parse.call_count == 2


@patch("cnki_mcp.core.tools.professional_search.ensure_login")
@patch("cnki_mcp.core.tools.professional_search.Runtime")
@patch("cnki_mcp.core.tools.professional_search.parse")
def test_run_submits_professional_expression(
    mock_parse: MagicMock,
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """run fills the expression and year range before one submission."""
    query = CnkiQuery(
        title="无心插柳",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
    )
    mock_page = MagicMock()
    mock_runtime = mock_runtime_cls.return_value.__enter__.return_value
    mock_runtime.get_page.return_value = mock_page
    mock_page.evaluate.return_value = {"submitted": True}
    mock_parse.return_value = [
        SearchResult(article_id="id1", title="无心插柳", year=2024)
    ]

    results = professional_search.run(query, profile="profile1", limit=1)

    mock_ensure_login.assert_called_once_with(profile="profile1")
    mock_page.goto.assert_called_once_with(
        professional_search.CNKI_PROFESSIONAL_SEARCH_URL,
        wait_until="domcontentloaded",
        timeout=professional_search.PAGE_LOAD_TIMEOUT_SECONDS * 1000,
    )
    payload = mock_page.evaluate.call_args.args[1]
    assert payload == {
        "expression": "TI='无心插柳'",
        "yearFrom": "2024",
        "yearTo": "2024",
    }
    mock_page.wait_for_timeout.assert_called_once_with(3000)
    mock_parse.assert_called_once_with(mock_page)
    assert results == mock_parse.return_value


@patch("cnki_mcp.core.tools.professional_search.ensure_login")
@patch("cnki_mcp.core.tools.professional_search.Runtime")
@patch("cnki_mcp.core.tools.professional_search._search_page")
def test_run_stops_after_source_fallback_finds_unique_result(
    mock_search_page: MagicMock,
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """An ambiguous title search adds source and then stops when unique."""
    first = SearchResult(article_id="id1", title="T")
    second = SearchResult(article_id="id2", title="T")
    unique = SearchResult(article_id="id1", title="T")
    mock_search_page.side_effect = [[first, second], [unique]]
    mock_runtime = mock_runtime_cls.return_value.__enter__.return_value
    mock_runtime.get_page.return_value = MagicMock()
    query = CnkiQuery(title="T", authors=["A"], source="S")

    assert professional_search._run(query, profile="profile1") == [unique]

    assert [call.args[1] for call in mock_search_page.call_args_list] == [
        "TI='T'",
        "TI='T' and LY='S'",
    ]
    mock_ensure_login.assert_called_once_with(profile="profile1")


@patch("cnki_mcp.core.tools.professional_search.ensure_login")
@patch("cnki_mcp.core.tools.professional_search.Runtime")
@patch("cnki_mcp.core.tools.professional_search._search_page")
def test_run_tries_author_after_source_returns_no_results(
    mock_search_page: MagicMock,
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """An empty source fallback does not hide a valid author fallback."""
    candidates = [
        SearchResult(article_id="id1", title="T"),
        SearchResult(article_id="id2", title="T"),
    ]
    unique = SearchResult(article_id="id1", title="T")
    mock_search_page.side_effect = [candidates, [], [unique]]
    mock_runtime = mock_runtime_cls.return_value.__enter__.return_value
    mock_runtime.get_page.return_value = MagicMock()
    query = CnkiQuery(title="T", authors=["A"], source="S")

    assert professional_search._run(query, profile="profile1") == [unique]

    assert [call.args[1] for call in mock_search_page.call_args_list] == [
        "TI='T'",
        "TI='T' and LY='S'",
        "TI='T' and AU='A'",
    ]


@patch("cnki_mcp.core.tools.professional_search.ensure_login")
@patch("cnki_mcp.core.tools.professional_search.Runtime")
@patch("cnki_mcp.core.tools.professional_search._search_page")
def test_run_does_not_retry_when_title_has_no_results(
    mock_search_page: MagicMock,
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """Stricter expressions cannot recover a title search with no matches."""
    mock_search_page.return_value = []
    mock_runtime = mock_runtime_cls.return_value.__enter__.return_value
    mock_runtime.get_page.return_value = MagicMock()
    query = CnkiQuery(title="T", authors=["A"], source="S")

    assert professional_search._run(query, profile="profile1") == []

    mock_search_page.assert_called_once()


@patch("cnki_mcp.core.tools.professional_search.ensure_login")
@patch("cnki_mcp.core.tools.professional_search.Runtime")
@patch("cnki_mcp.core.tools.professional_search.parse")
def test_run_wraps_parse_error(
    mock_parse: MagicMock,
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """ParseError is exposed as a SearchError."""
    mock_page = MagicMock()
    mock_runtime = mock_runtime_cls.return_value.__enter__.return_value
    mock_runtime.get_page.return_value = mock_page
    mock_page.evaluate.return_value = {"submitted": True}
    mock_parse.side_effect = ParseError("bad html")

    with pytest.raises(SearchError, match="failed to parse"):
        professional_search.run(CnkiQuery(title="query"), profile="profile1")

    assert mock_ensure_login.called


@patch("cnki_mcp.core.tools.professional_search.ensure_login")
@patch("cnki_mcp.core.tools.professional_search.Runtime")
def test_run_reports_missing_professional_form(
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """A missing professional-search form produces a clear error."""
    mock_page = MagicMock()
    mock_runtime = mock_runtime_cls.return_value.__enter__.return_value
    mock_runtime.get_page.return_value = mock_page
    mock_page.evaluate.return_value = {
        "submitted": False,
        "error": "professional-search textarea unavailable",
    }

    with pytest.raises(SearchError, match="textarea unavailable"):
        professional_search.run(CnkiQuery(title="query"), profile="profile1")

    assert mock_ensure_login.called


def test_turn_to_page_reports_timeout() -> None:
    """Pagination never parses a stale result page after a timeout."""
    mock_page = MagicMock()
    mock_page.evaluate.return_value = True
    mock_page.wait_for_function.side_effect = TimeoutError("stale page")

    with pytest.raises(SearchError, match="page 2"):
        professional_search._turn_to_page(mock_page, 2)
