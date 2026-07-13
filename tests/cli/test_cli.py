#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/cli/test_cli.py

"""Tests for the cnki-mcp CLI."""

import json
from unittest.mock import MagicMock, patch

import pytest

from cnki_mcp.cli.main import _build_parser, _format_output, main
from cnki_mcp.core.exceptions import CnkiMcpError
from cnki_mcp.core.models import Article, AuthState, LoginResult, SearchResult
from cnki_mcp.core.retrieval.models import MetadataLookupResult


def test_format_output_json() -> None:
    """JSON output contains the input data."""
    s = _format_output({"title": "Example"}, "json")
    assert '"title": "Example"' in s


def test_format_output_text() -> None:
    """Text output stringifies the data."""
    s = _format_output({"title": "Example"}, "text")
    assert "Example" in s


def test_format_output_unsupported() -> None:
    """Unsupported format raises ValueError."""
    with pytest.raises(ValueError):
        _format_output({}, "xml")


def test_search_help_includes_professional_search_guide(capsys) -> None:
    """Search help explains CNKI fields and expression examples."""
    parser = _build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["search", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "SU=主题" in help_text
    assert "TI=篇名" in help_text
    assert "AU=作者" in help_text
    assert "TI='生态'" in help_text
    assert "FT='环境保护'" in help_text


@patch("cnki_mcp.cli.main.CnkiClient")
def test_search_subcommand_calls_client(
    mock_client_cls: MagicMock,
    capsys,
) -> None:
    """search invokes client.search and prints JSON."""
    mock_client = mock_client_cls.return_value
    mock_client.search.return_value = [
        SearchResult(
            article_id="id1",
            title="Title 1",
            authors=["Author 1"],
            source="Journal 1",
            date="2026-02-25",
        ),
    ]
    code = main(["search", "劳动经济学", "--limit", "5"])
    assert code == 0
    mock_client.search.assert_called_once_with("劳动经济学", limit=5)
    payload = json.loads(capsys.readouterr().out)
    assert payload == [
        {
            "title": "Title 1",
            "authors": ["Author 1"],
            "journal": "Journal 1",
            "date": "2026-02-25",
        }
    ]


@patch("cnki_mcp.cli.main.CnkiClient")
def test_search_subcommand_passes_filters(mock_client_cls: MagicMock) -> None:
    """search forwards filter options to client.search."""
    mock_client = mock_client_cls.return_value
    mock_client.search.return_value = [
        SearchResult(article_id="id1", title="Title 1"),
    ]
    code = main(
        [
            "search",
            "人工智能",
            "--year-from",
            "2025",
            "--year-to",
            "2026",
            "--journal",
            "图书馆论坛",
            "--document-type",
            "journal",
            "--source-type",
            "CSSCI",
            "--sort-by",
            "date",
        ]
    )
    assert code == 0
    mock_client.search.assert_called_once_with(
        "人工智能",
        limit=10,
        sort_by="date",
        year_from=2025,
        year_to=2026,
        journal="图书馆论坛",
        document_type="journal",
        source_types=["CSSCI"],
    )


@patch("cnki_mcp.cli.main.CnkiClient")
def test_metadata_subcommand_calls_client(mock_client_cls: MagicMock) -> None:
    """metadata invokes client.get_metadata and prints JSON."""
    mock_client = mock_client_cls.return_value
    mock_client.get_metadata.return_value = Article(
        article_id="aid",
        title="Article Title",
    )
    code = main(["metadata", "aid"])
    assert code == 0
    mock_client.get_metadata.assert_called_once_with("aid")


@patch("cnki_mcp.cli.main.CnkiClient")
def test_lookup_metadata_subcommand_calls_client(mock_client_cls: MagicMock) -> None:
    """lookup-metadata forwards structured citation fields."""
    mock_client = mock_client_cls.return_value
    mock_client.lookup_metadata.return_value = MetadataLookupResult()
    code = main(
        [
            "lookup-metadata",
            "无心插柳",
            "--author",
            "袁晓燕",
            "--author",
            "翁士汉",
            "--year",
            "2024",
            "--source",
            "世界经济文汇",
            "--limit",
            "20",
        ]
    )

    assert code == 0
    mock_client.lookup_metadata.assert_called_once_with(
        "无心插柳",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
        document_type=None,
        limit=20,
    )


@patch("cnki_mcp.cli.main.CnkiClient")
def test_login_subcommand_calls_client(mock_client_cls: MagicMock) -> None:
    """login invokes client.login and prints JSON."""
    mock_client = mock_client_cls.return_value
    mock_client.login.return_value = LoginResult(
        success=True,
        message="ok",
        auth_state=AuthState(is_logged_in=True, profile="profile1"),
    )
    code = main(["login", "--profile", "profile1"])
    assert code == 0
    mock_client_cls.assert_called_once_with(profile="profile1")
    mock_client.login.assert_called_once()


@patch("cnki_mcp.cli.main.CnkiClient")
def test_logout_subcommand_calls_client(mock_client_cls: MagicMock) -> None:
    """logout invokes client.logout and prints JSON."""
    mock_client = mock_client_cls.return_value
    mock_client.current_profile = "profile1"
    code = main(["logout", "--profile", "profile1"])
    assert code == 0
    mock_client.logout.assert_called_once()


@patch("cnki_mcp.cli.main.CnkiClient")
def test_profile_passthrough(mock_client_cls: MagicMock) -> None:
    """--profile is forwarded to CnkiClient."""
    main(["search", "query", "--profile", "profile2"])
    mock_client_cls.assert_called_once_with(profile="profile2")


@patch("cnki_mcp.cli.main.CnkiClient")
def test_output_json_format(mock_client_cls: MagicMock, capsys) -> None:
    """--output json prints valid JSON."""
    mock_client = mock_client_cls.return_value
    mock_client.search.return_value = [SearchResult(article_id="id", title="T")]
    main(["search", "query", "--output", "json"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)


@patch("cnki_mcp.cli.main.CnkiClient")
def test_error_returns_nonzero(mock_client_cls: MagicMock) -> None:
    """CnkiMcpError causes a non-zero exit code."""
    mock_client = mock_client_cls.return_value
    mock_client.search.side_effect = CnkiMcpError("boom")
    code = main(["search", "query"])
    assert code != 0
