#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/server/test_cnki_mcp_server.py

"""Tests for server/cnki_mcp_server.py."""

import inspect
from unittest.mock import MagicMock, patch

from cnki_mcp.core.exceptions import CnkiMcpError
from cnki_mcp.core.models import Article, AuthState, LoginResult, SearchResult
from cnki_mcp.core.retrieval.models import MetadataLookupResult
from cnki_mcp.server.cnki_mcp_server import (
    _to_dict,
    cnki_get_metadata,
    cnki_login,
    cnki_logout,
    cnki_lookup_metadata,
    cnki_search,
    mcp_server,
)


def test_cnki_search_tool_description_includes_professional_guide() -> None:
    """The MCP tool description documents fields and examples."""
    description = inspect.getdoc(cnki_search) or ""

    assert "SU=主题" in description
    assert "TI=篇名" in description
    assert "AU=作者" in description
    assert "TI='生态'" in description


def test_mcp_server_instance_exists() -> None:
    """mcp_server is a FastMCP instance."""
    assert mcp_server is not None


def test_to_dict_handles_datetime_and_path() -> None:
    """_to_dict serializes datetime and Path objects."""
    result = SearchResult(
        article_id="id",
        title="T",
    )
    data = _to_dict(result)
    assert data["article_id"] == "id"
    assert data["title"] == "T"


@patch("cnki_mcp.server.cnki_mcp_server.CnkiClient")
def test_cnki_search_returns_dict_list(mock_client_cls: MagicMock) -> None:
    """cnki_search returns a list of dictionaries."""
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_client.search.return_value = [
        SearchResult(
            article_id="id1",
            title="Title 1",
            authors=["Author 1"],
            source="Journal 1",
            date="2026-02-25",
        ),
    ]
    results = cnki_search("query", limit=5, profile="profile1")
    assert isinstance(results, list)
    assert results == [
        {
            "title": "Title 1",
            "authors": ["Author 1"],
            "journal": "Journal 1",
            "date": "2026-02-25",
        }
    ]
    mock_client_cls.assert_called_once_with(profile="profile1")


@patch("cnki_mcp.server.cnki_mcp_server.CnkiClient")
def test_cnki_search_forwards_filters(mock_client_cls: MagicMock) -> None:
    """cnki_search forwards optional filter arguments."""
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_client.search.return_value = [
        SearchResult(article_id="id1", title="Title 1"),
    ]
    cnki_search(
        "query",
        limit=5,
        sort_by="citation",
        profile="profile1",
        year_from=2025,
        year_to=2026,
        journal="图书馆论坛",
        document_type="journal",
        source_types=["CSSCI"],
    )
    mock_client.search.assert_called_once_with(
        "query",
        limit=5,
        sort_by="citation",
        year_from=2025,
        year_to=2026,
        journal="图书馆论坛",
        document_type="journal",
        source_types=["CSSCI"],
        author=None,
        institution=None,
    )


@patch("cnki_mcp.server.cnki_mcp_server.CnkiClient")
def test_cnki_get_metadata_returns_dict(mock_client_cls: MagicMock) -> None:
    """cnki_get_metadata returns a dictionary."""
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_client.get_metadata.return_value = Article(
        article_id="aid",
        title="Article",
    )
    result = cnki_get_metadata("aid", profile="profile1")
    assert isinstance(result, dict)
    assert result["title"] == "Article"


@patch("cnki_mcp.server.cnki_mcp_server.CnkiClient")
def test_cnki_lookup_metadata_returns_nested_dict(
    mock_client_cls: MagicMock,
) -> None:
    """cnki_lookup_metadata serializes the structured lookup result."""
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_client.lookup_metadata.return_value = MetadataLookupResult(
        article=Article(article_id="aid", title="目标文章"),
        is_unique=True,
    )

    result = cnki_lookup_metadata(
        "目标文章",
        authors=["作者甲"],
        year=2026,
        source="中国社会科学",
        limit=20,
        profile="profile1",
    )

    assert result["article"]["title"] == "目标文章"
    assert result["is_unique"] is True
    mock_client.lookup_metadata.assert_called_once_with(
        "目标文章",
        authors=["作者甲"],
        year=2026,
        source="中国社会科学",
        document_type=None,
        limit=20,
    )


@patch("cnki_mcp.server.cnki_mcp_server.CnkiClient")
def test_cnki_login_returns_result(mock_client_cls: MagicMock) -> None:
    """cnki_login returns a result dictionary."""
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_client.login.return_value = LoginResult(
        success=True,
        message="ok",
        auth_state=AuthState(is_logged_in=True, profile="profile1"),
    )
    result = cnki_login(profile="profile1")
    assert result["success"] is True
    assert result["profile"] == "profile1"


@patch("cnki_mcp.server.cnki_mcp_server.CnkiClient")
def test_cnki_logout_returns_success(mock_client_cls: MagicMock) -> None:
    """cnki_logout returns a success dictionary."""
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_client.current_profile = "profile1"
    result = cnki_logout(profile="profile1")
    assert result["success"] is True
    mock_client.logout.assert_called_once()


@patch("cnki_mcp.server.cnki_mcp_server.CnkiClient")
def test_cnki_search_catches_cnki_mcp_error(mock_client_cls: MagicMock) -> None:
    """CnkiMcpError is caught and returned as an error dict."""
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_client.search.side_effect = CnkiMcpError("boom")
    results = cnki_search("query")
    assert results[0]["success"] is False
    assert "boom" in results[0]["error"]
