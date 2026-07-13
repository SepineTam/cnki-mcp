#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/parsers/test_search.py

"""Tests for core/tools/search.py."""

from unittest.mock import MagicMock, patch

from cnki_mcp.core.models import SearchFilters, SearchResult
from cnki_mcp.core.retrieval.models import CnkiQuery
from cnki_mcp.core.tools import search


def test_build_filter_payload_normalizes_filters() -> None:
    """Result facets are normalized for the professional result page."""
    filters = SearchFilters(
        year_from=2025,
        year_to=2026,
        journal="图书馆论坛",
        document_type="journal",
        source_types=["CSSCI", "北大核心"],
        author="刘炜",
        institution="上海大学",
    )
    payload = search._build_filter_payload(filters)
    assert payload["documentType"] == "学术期刊"
    group_filters = payload["groupFilters"]
    assert len(group_filters) == 1
    source_filter = group_filters[0]
    source_codes = {item["Value"] for item in source_filter["items"]}
    assert source_codes == {"P0209", "P01"}
    assert search._normalize_year_range(filters) == (2025, 2026)


@patch("cnki_mcp.core.tools.search.professional_search._run_expression")
def test_run_uses_professional_search_for_plain_title(
    mock_expression_run: MagicMock,
) -> None:
    """Plain titles and every optional filter stay on professional search."""
    mock_expression_run.return_value = [
        SearchResult(article_id="id1", title="T1"),
        SearchResult(article_id="id2", title="T2"),
    ]
    results = search.run(
        "目标论文",
        profile="profile1",
        limit=1,
        year_from=2026,
        year_to=2026,
        journal="中国社会科学",
        document_type="journal",
        author="陆铭",
        institution="复旦大学",
        source_types=["CSSCI"],
    )

    call = mock_expression_run.call_args
    assert call.args[0] == (
        "TI='目标论文' and LY='中国社会科学' "
        "and AU='陆铭' and AF='复旦大学'"
    )
    assert call.kwargs["year_from"] == 2026
    assert call.kwargs["year_to"] == 2026
    assert call.kwargs["filter_payload"]["documentType"] == "学术期刊"
    source_filter = call.kwargs["filter_payload"]["groupFilters"][0]
    assert source_filter["key"] == "LYBSM"
    assert source_filter["items"][0]["Value"] == "P0209"
    assert call.kwargs["profile"] == "profile1"
    assert call.kwargs["limit"] == 1
    assert call.kwargs["max_pages"] == 1
    assert call.kwargs["sort_by"] is None
    assert len(results) == 1
    assert results[0].title == "T1"


@patch("cnki_mcp.core.tools.search.professional_search._run_expression")
def test_run_uses_professional_search_for_year_range_and_source_types(
    mock_expression_run: MagicMock,
) -> None:
    """Year ranges and source facets never fall back to one-box search."""
    mock_expression_run.return_value = []

    search.run(
        "TI='人工智能'",
        year_from=2020,
        year_to=2026,
        source_types=["CSSCI", "北大核心"],
        institution="上海大学",
    )

    call = mock_expression_run.call_args
    assert call.args[0] == "(TI='人工智能') and AF='上海大学'"
    assert call.kwargs["year_from"] == 2020
    assert call.kwargs["year_to"] == 2026
    codes = {
        item["Value"]
        for item in call.kwargs["filter_payload"]["groupFilters"][0]["items"]
    }
    assert codes == {"P0209", "P01"}
    assert call.kwargs["profile"] is None
    assert call.kwargs["limit"] == 10
    assert call.kwargs["max_pages"] == 1
    assert call.kwargs["sort_by"] is None


@patch("cnki_mcp.core.tools.search.professional_search._run")
def test_structured_query_also_uses_professional_search_with_filters(
    mock_professional_run: MagicMock,
) -> None:
    """Structured queries remain professional when result filters are supplied."""
    query = CnkiQuery(title="目标论文", year=2024)
    mock_professional_run.return_value = []

    search.run(
        query,
        year_from=2023,
        year_to=2025,
        document_type="journal",
        source_types=["CSSCI"],
    )

    assert mock_professional_run.call_args.args == (query,)
    assert mock_professional_run.call_args.kwargs["year_from"] == 2023
    assert mock_professional_run.call_args.kwargs["year_to"] == 2025
    assert mock_professional_run.call_args.kwargs["filter_payload"][
        "documentType"
    ] == "学术期刊"
    assert mock_professional_run.call_args.kwargs["profile"] is None
    assert mock_professional_run.call_args.kwargs["limit"] == 10
    assert mock_professional_run.call_args.kwargs["max_pages"] == 1
    assert mock_professional_run.call_args.kwargs["sort_by"] is None


@patch("cnki_mcp.core.tools.search.professional_search._run")
def test_run_preserves_all_authors_from_structured_query(
    mock_professional_run: MagicMock,
) -> None:
    """A structured query reaches professional search without field loss."""
    query = CnkiQuery(
        title="无心插柳——世界杯爆冷获胜的贸易创造",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
        document_type="journal",
    )
    mock_professional_run.return_value = []

    search.run(query, profile="profile1", limit=5, max_pages=2)

    mock_professional_run.assert_called_once_with(
        query,
        profile="profile1",
        limit=5,
        max_pages=2,
        year_from=None,
        year_to=None,
        filter_payload={
            "documentType": None,
            "groupFilters": [],
            "defaultFilterProducts": search.DEFAULT_FILTER_PRODUCTS,
        },
        sort_by=None,
    )


@patch("cnki_mcp.core.tools.search.professional_search._run_expression")
def test_run_passes_professional_expression_without_title_wrapping(
    mock_expression_run: MagicMock,
) -> None:
    """A fielded expression is submitted without converting it to TI text."""
    expression = "SU='北京' * '奥运' and FT='环境保护'"
    mock_expression_run.return_value = []

    search.run(expression, profile="profile1", limit=5)

    mock_expression_run.assert_called_once_with(
        f"({expression})",
        year_from=None,
        year_to=None,
        filter_payload={
            "documentType": None,
            "groupFilters": [],
            "defaultFilterProducts": search.DEFAULT_FILTER_PRODUCTS,
        },
        sort_by=None,
        profile="profile1",
        limit=5,
        max_pages=1,
    )
