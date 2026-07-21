#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/test_client.py

"""Tests for core/client.py."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cnki_mcp.core import config
from cnki_mcp.core.client import CnkiClient
from cnki_mcp.core.models import Article, JournalIssue, SearchResult
from cnki_mcp.core.retrieval.models import CnkiQuery, MetadataLookupResult


def test_search_api_docstring_includes_professional_guide() -> None:
    """The Python API docstring documents professional fields and examples."""
    description = CnkiClient.search.__doc__ or ""

    assert "SU=主题" in description
    assert "TI=篇名" in description
    assert "AU=作者" in description
    assert "TI='生态'" in description


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path) -> Iterator[None]:
    """Redirect config paths into a temporary directory."""
    profiles = tmp_path / "profiles"
    with patch.object(config, "BASE_DIR", tmp_path):
        with patch.object(config, "PROFILES_DIR", profiles):
            with patch.object(config, "PROFILE_CONFIG_PATH", profiles / "config.json"):
                yield


def test_client_default_profile() -> None:
    """Client resolves to the default profile."""
    client = CnkiClient()
    assert client.current_profile == "profile1"


def test_client_explicit_profile() -> None:
    """Client accepts an explicit profile."""
    client = CnkiClient(profile="profile2")
    assert client.current_profile == "profile2"


@patch("cnki_mcp.core.client.ensure_login")
@patch("cnki_mcp.core.client.search.run")
def test_search_ensures_login_and_calls_tool(
    mock_search: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """search ensures login then delegates to the search tool."""
    mock_search.return_value = [SearchResult(article_id="id", title="T")]
    client = CnkiClient(profile="profile1")
    results = client.search("query", limit=3)
    mock_ensure_login.assert_called_once()
    mock_search.assert_called_once()
    assert len(results) == 1
    assert results[0].title == "T"


@patch("cnki_mcp.core.client.ensure_login")
@patch("cnki_mcp.core.client.search.run")
def test_search_forwards_filter_kwargs(
    mock_search: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """search forwards filter kwargs to the search tool."""
    mock_search.return_value = [SearchResult(article_id="id", title="T")]
    client = CnkiClient(profile="profile1")
    client.search(
        "query",
        limit=3,
        sort_by="date",
        year_from=2025,
        year_to=2026,
        journal="图书馆论坛",
    )
    mock_ensure_login.assert_called_once()
    assert mock_search.call_args.kwargs["year_from"] == 2025
    assert mock_search.call_args.kwargs["year_to"] == 2026
    assert mock_search.call_args.kwargs["journal"] == "图书馆论坛"
    assert mock_search.call_args.kwargs["sort_by"] == "date"


@patch("cnki_mcp.core.client.ensure_login")
@patch("cnki_mcp.core.client.basic_search.run")
def test_search_basic_uses_one_box_tool(
    mock_basic_search: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """The explicit basic-search facade uses the one-box operation."""
    mock_basic_search.return_value = [SearchResult(article_id="id", title="T")]
    client = CnkiClient(profile="profile1")

    results = client.search_basic("数字经济", limit=5, sort_by="date")

    mock_ensure_login.assert_called_once()
    mock_basic_search.assert_called_once_with(
        "数字经济",
        profile="profile1",
        limit=5,
        sort_by="date",
        filters=None,
    )
    assert results == mock_basic_search.return_value


@patch("cnki_mcp.core.client.ensure_login")
@patch("cnki_mcp.core.client.metadata.run")
def test_get_metadata_ensures_login_and_calls_tool(
    mock_metadata: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """get_metadata ensures login then delegates to the metadata tool."""
    mock_metadata.return_value = Article(article_id="aid", title="Article")
    client = CnkiClient(profile="profile1")
    article = client.get_metadata("aid")
    mock_ensure_login.assert_called_once()
    mock_metadata.assert_called_once_with("aid", profile="profile1")
    assert article.title == "Article"


@patch("cnki_mcp.core.client.ensure_login")
@patch("cnki_mcp.core.client.journal.run")
def test_list_journal_ensures_login_and_calls_tool(
    mock_journal: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """The facade exposes issue listing by its unique ISSN."""
    mock_journal.return_value = JournalIssue(
        name="世界经济",
        year=2026,
        issue="01",
    )
    client = CnkiClient(profile="profile1")

    result = client.list_journal(issn="1002-9621", year=2026, vol=1)

    mock_ensure_login.assert_called_once()
    mock_journal.assert_called_once_with(
        issn="1002-9621",
        year=2026,
        vol=1,
        profile="profile1",
    )
    assert result.issue == "01"


@patch("cnki_mcp.core.client.ensure_login")
@patch("cnki_mcp.core.client.journal.search_issn")
def test_search_issn_ensures_login_and_calls_tool(
    mock_search_issn: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """The facade resolves a journal name to the requested mapping."""
    mock_search_issn.return_value = {"世界经济": "1002-9621"}
    client = CnkiClient(profile="profile1")

    result = client.search_issn(journal="世界经济")

    mock_ensure_login.assert_called_once()
    mock_search_issn.assert_called_once_with("世界经济", profile="profile1")
    assert result == {"世界经济": "1002-9621"}


@patch("cnki_mcp.core.client.ensure_login")
@patch("cnki_mcp.core.client.metadata_lookup.lookup")
def test_lookup_metadata_builds_cnki_query(
    mock_lookup: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """lookup_metadata builds a structured CNKI query."""
    mock_lookup.return_value = MetadataLookupResult()
    client = CnkiClient(profile="profile1")

    result = client.lookup_metadata(
        "无心插柳",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
        document_type="journal",
    )

    mock_ensure_login.assert_called_once()
    query = mock_lookup.call_args.args[0]
    assert query == CnkiQuery(
        title="无心插柳",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
        document_type="journal",
    )
    assert mock_lookup.call_args.kwargs == {"profile": "profile1", "limit": 10}
    assert result is mock_lookup.return_value


@patch("cnki_mcp.core.client.login")
def test_login_delegates_to_auth(mock_login: MagicMock) -> None:
    """client.login delegates to auth.login."""
    client = CnkiClient(profile="profile1")
    client.login()
    mock_login.assert_called_once()
    assert mock_login.call_args.kwargs["profile"] == "profile1"


@patch("cnki_mcp.core.client.logout")
def test_logout_delegates_to_auth(mock_logout: MagicMock) -> None:
    """client.logout delegates to auth.logout."""
    client = CnkiClient(profile="profile1")
    client.logout()
    mock_logout.assert_called_once_with(profile="profile1")


def test_client_context_manager() -> None:
    """CnkiClient supports the with statement."""
    with CnkiClient(profile="profile1") as client:
        assert client.current_profile == "profile1"
