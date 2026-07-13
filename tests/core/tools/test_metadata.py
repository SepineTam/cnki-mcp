#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/parsers/test_metadata.py

"""Tests for core/tools/metadata.py."""

from unittest.mock import MagicMock, patch

import pytest

from cnki_mcp.core.exceptions import MetadataError, ParseError
from cnki_mcp.core.models import Article
from cnki_mcp.core.tools import metadata


def test_build_detail_url_contains_article_id() -> None:
    """build_detail_url returns a URL containing the article id."""
    url = metadata.build_detail_url("abc123")
    assert isinstance(url, str)
    assert "abc123" in url


@patch("cnki_mcp.core.tools.metadata.ensure_login")
@patch("cnki_mcp.core.tools.metadata.Runtime")
@patch("cnki_mcp.core.tools.metadata.parse")
def test_run_calls_dependencies(
    mock_parse: MagicMock,
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """run orchestrates login, runtime, navigation, and parsing."""
    mock_page = MagicMock()
    mock_runtime = mock_runtime_cls.return_value.__enter__.return_value
    mock_runtime.get_page.return_value = mock_page
    mock_parse.return_value = Article(article_id="abc123", title="Article")
    article = metadata.run("abc123", profile="profile1")
    mock_ensure_login.assert_called_once_with(profile="profile1")
    mock_page.goto.assert_called_once()
    mock_parse.assert_called_once_with(mock_page)
    assert article.article_id == "abc123"
    assert article.title == "Article"


@patch("cnki_mcp.core.tools.metadata.ensure_login")
@patch("cnki_mcp.core.tools.metadata.Runtime")
@patch("cnki_mcp.core.tools.metadata.parse")
def test_run_wraps_parse_error(
    mock_parse: MagicMock,
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """ParseError is wrapped as MetadataError."""
    mock_page = MagicMock()
    mock_runtime = mock_runtime_cls.return_value.__enter__.return_value
    mock_runtime.get_page.return_value = mock_page
    mock_parse.side_effect = ParseError("bad html")
    with pytest.raises(MetadataError):
        metadata.run("abc123", profile="profile1")
    assert mock_ensure_login.called
