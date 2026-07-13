#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/tools/test_basic_search.py

"""Tests for the CNKI one-box search operation."""

from unittest.mock import MagicMock, patch

import pytest

from cnki_mcp.core.exceptions import SearchError
from cnki_mcp.core.models import SearchResult
from cnki_mcp.core.tools import basic_search


def test_build_search_url_uses_one_box_subject_field() -> None:
    """Basic text is encoded for the CNKI one-box subject search."""
    url = basic_search.build_search_url("数字 经济")

    assert "defaultresult/index" in url
    assert "korder=SU" in url
    assert "kw=%E6%95%B0%E5%AD%97+%E7%BB%8F%E6%B5%8E" in url


def test_local_filters_match_year_journal_and_author() -> None:
    """Fields present in one-box results can be filtered locally."""
    right = SearchResult(
        article_id="right",
        title="T",
        authors=["张三", "李四"],
        year=2026,
        source="图书馆论坛",
    )
    wrong = SearchResult(
        article_id="wrong",
        title="T",
        authors=["王五"],
        year=2024,
        source="其他期刊",
    )

    assert basic_search._filter_results(
        [wrong, right],
        year_from=2025,
        year_to=2026,
        journal="图书馆论坛",
        author="张三",
    ) == [right]


def test_institution_filter_requires_advanced_search() -> None:
    """One-box rows do not expose institutions for reliable filtering."""
    with pytest.raises(SearchError, match="advanced"):
        basic_search._validate_options(limit=10, max_pages=1, institution="上海大学")


@patch("cnki_mcp.core.tools.basic_search.ensure_login")
@patch("cnki_mcp.core.tools.basic_search.Runtime")
@patch("cnki_mcp.core.tools.basic_search.parse")
def test_run_opens_one_box_and_applies_sort(
    mock_parse: MagicMock,
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """Basic search navigates to one-box results and applies result ordering."""
    page = MagicMock()
    runtime = mock_runtime_cls.return_value.__enter__.return_value
    runtime.get_page.return_value = page
    mock_parse.return_value = [SearchResult(article_id="id", title="T", year=2026)]
    page.evaluate.return_value = {"applied": True}

    results = basic_search.run(
        "人工智能",
        profile="school",
        sort_by="date",
        year_from=2026,
        year_to=2026,
    )

    mock_ensure_login.assert_called_once_with(profile="school")
    assert "defaultresult/index" in page.goto.call_args.args[0]
    assert page.evaluate.call_args.args[1] == "PT"
    assert results == mock_parse.return_value
