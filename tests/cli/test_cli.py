#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/cli/test_cli.py

"""Tests for the unified cnki-mcp CLI."""

import json
from unittest.mock import MagicMock, patch

import pytest

from cnki_mcp.cli.main import _format_output, main
from cnki_mcp.core.exceptions import CnkiMcpError
from cnki_mcp.core.models import Article, AuthState, LoginResult, SearchResult
from cnki_mcp.core.retrieval.models import MetadataLookupResult


def test_format_output_json() -> None:
    """JSON output contains the input data."""
    output = _format_output({"title": "Example"}, "json")
    assert '"title": "Example"' in output


def test_format_output_text() -> None:
    """Text output stringifies the data."""
    assert "Example" in _format_output({"title": "Example"}, "text")


def test_format_output_unsupported() -> None:
    """Unsupported output formats are rejected."""
    with pytest.raises(ValueError):
        _format_output({}, "xml")


def test_help_uses_unified_program_name(capsys) -> None:
    """Top-level help describes the one public executable."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "usage: cnki-mcp" in help_text
    assert "serve" in help_text
    assert "tool" in help_text
    assert "login" in help_text
    assert "logout" in help_text


def test_version_is_available_without_starting_server(capsys) -> None:
    """Both short and long version flags print and exit immediately."""
    for option in ("-v", "--version"):
        with pytest.raises(SystemExit) as exc_info:
            main([option])
        assert exc_info.value.code == 0
        assert "cnki-mcp" in capsys.readouterr().out


@patch("cnki_mcp.cli.main.ensure_login", create=True)
@patch("cnki_mcp.cli.main.mcp_server", create=True)
def test_no_arguments_start_default_http_server(
    mock_server: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """Bare cnki-mcp starts HTTP on the documented default address."""
    assert main([]) == 0

    mock_ensure_login.assert_called_once_with(profile=None)
    assert mock_server.settings.host == "127.0.0.1"
    assert mock_server.settings.port == 7788
    mock_server.run.assert_called_once_with(transport="streamable-http")


@patch("cnki_mcp.cli.main.ensure_login", create=True)
@patch("cnki_mcp.cli.main.mcp_server", create=True)
def test_serve_maps_public_http_name_to_fastmcp_transport(
    mock_server: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """The public http name maps to FastMCP streamable HTTP."""
    code = main(
        [
            "serve",
            "--transport",
            "http",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
        ]
    )

    assert code == 0
    mock_ensure_login.assert_called_once_with(profile=None)
    assert mock_server.settings.host == "0.0.0.0"
    assert mock_server.settings.port == 9000
    mock_server.run.assert_called_once_with(transport="streamable-http")


@patch("cnki_mcp.cli.main.ensure_login", create=True)
@patch("cnki_mcp.cli.main.mcp_server", create=True)
def test_sse_warns_and_starts(
    mock_server: MagicMock,
    mock_ensure_login: MagicMock,
    capsys,
) -> None:
    """SSE stays available but recommends HTTP on stderr."""
    assert main(["serve", "--transport", "sse"]) == 0

    assert "HTTP" in capsys.readouterr().err
    mock_server.run.assert_called_once_with(transport="sse")


@patch("cnki_mcp.cli.main.ensure_login", create=True)
@patch("cnki_mcp.cli.main.mcp_server", create=True)
def test_stdio_starts_only_when_explicitly_selected(
    mock_server: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """Stdio is available only through the explicit serve option."""
    assert main(["serve", "--transport", "stdio"]) == 0
    mock_server.run.assert_called_once_with(transport="stdio")


@patch("cnki_mcp.cli.main.ensure_login", create=True)
@patch("cnki_mcp.cli.main.mcp_server", create=True)
def test_server_keyboard_interrupt_exits_cleanly(
    mock_server: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    """Ctrl+C stops a running server without exposing a traceback."""
    mock_server.run.side_effect = KeyboardInterrupt

    assert main(["serve"]) == 0


@pytest.mark.parametrize("option", ["--host", "--port"])
def test_stdio_rejects_network_options(option: str) -> None:
    """Host and port have no meaning for stdio and are rejected."""
    value = "127.0.0.1" if option == "--host" else "7788"
    with pytest.raises(SystemExit) as exc_info:
        main(["serve", "--transport", "stdio", option, value])
    assert exc_info.value.code == 2


@pytest.mark.parametrize("command", [["login"], ["logout"], ["tool", "search", "T"]])
def test_network_options_belong_only_to_serve(command: list[str]) -> None:
    """Other command branches do not accept server network options."""
    with pytest.raises(SystemExit) as exc_info:
        main([*command, "--host", "127.0.0.1"])
    assert exc_info.value.code == 2


@patch("cnki_mcp.cli.main.CnkiClient")
def test_tool_search_uses_one_box_by_default(
    mock_client_cls: MagicMock,
    capsys,
) -> None:
    """A positional search query uses the one-box search operation."""
    client = mock_client_cls.return_value
    client.search_basic.return_value = [
        SearchResult(
            article_id="id1",
            title="Title 1",
            authors=["Author 1"],
            source="Journal 1",
            date="2026-02-25",
        )
    ]

    assert main(["tool", "search", "劳动经济学", "--limit", "5"]) == 0

    client.search_basic.assert_called_once_with("劳动经济学", limit=5)
    assert json.loads(capsys.readouterr().out) == [
        {
            "title": "Title 1",
            "authors": ["Author 1"],
            "journal": "Journal 1",
            "date": "2026-02-25",
        }
    ]


@patch("cnki_mcp.cli.main.CnkiClient")
def test_tool_search_advanced_uses_professional_search(
    mock_client_cls: MagicMock,
) -> None:
    """The advanced option sends a professional expression unchanged."""
    client = mock_client_cls.return_value
    client.search.return_value = []

    assert main(["tool", "search", "--advanced", "TI='生态'"]) == 0

    client.search.assert_called_once_with("TI='生态'", limit=10)
    client.search_basic.assert_not_called()


@patch("cnki_mcp.cli.main.CnkiClient")
def test_tool_search_passes_shared_filters(mock_client_cls: MagicMock) -> None:
    """Basic search receives the supported filters and ordering options."""
    client = mock_client_cls.return_value
    client.search_basic.return_value = []

    code = main(
        [
            "tool",
            "search",
            "人工智能",
            "--year-from",
            "2025",
            "--year-to",
            "2026",
            "--journal",
            "图书馆论坛",
            "--author",
            "张三",
            "--document-type",
            "journal",
            "--source-type",
            "CSSCI",
            "--sort-by",
            "date",
        ]
    )

    assert code == 0
    client.search_basic.assert_called_once_with(
        "人工智能",
        limit=10,
        sort_by="date",
        year_from=2025,
        year_to=2026,
        journal="图书馆论坛",
        author="张三",
        document_type="journal",
        source_types=["CSSCI"],
    )


def test_tool_search_requires_exactly_one_query_mode() -> None:
    """Basic text and an advanced expression cannot be mixed or omitted."""
    with pytest.raises(SystemExit):
        main(["tool", "search"])
    with pytest.raises(SystemExit):
        main(["tool", "search", "生态", "--advanced", "TI='生态'"])


@patch("cnki_mcp.cli.main.CnkiClient")
def test_tool_info_url_parses_directly(
    mock_client_cls: MagicMock,
    capsys,
) -> None:
    """A CNKI URL is sent directly to the detail parser workflow."""
    url = "https://kns.cnki.net/kcms2/article/abstract?v=abc"
    client = mock_client_cls.return_value
    client.get_metadata.return_value = Article(article_id=url, title="文章")

    assert main(["tool", "info", url]) == 0

    client.get_metadata.assert_called_once_with(url)
    assert json.loads(capsys.readouterr().out)["title"] == "文章"


@patch("cnki_mcp.cli.main.CnkiClient")
def test_tool_info_title_resolves_then_parses(
    mock_client_cls: MagicMock,
) -> None:
    """Citation fields use the lookup workflow through the same info command."""
    client = mock_client_cls.return_value
    client.lookup_metadata.return_value = MetadataLookupResult()

    code = main(
        [
            "tool",
            "info",
            "--title",
            "无心插柳",
            "--author",
            "袁晓燕",
            "--author",
            "翁士汉",
            "--year",
            "2024",
            "--journal",
            "世界经济文汇",
            "--limit",
            "20",
        ]
    )

    assert code == 0
    client.lookup_metadata.assert_called_once_with(
        "无心插柳",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
        document_type=None,
        limit=20,
    )


def test_tool_info_requires_url_or_title_but_not_both() -> None:
    """Info input modes are mutually exclusive."""
    with pytest.raises(SystemExit):
        main(["tool", "info"])
    with pytest.raises(SystemExit):
        main(
            [
                "tool",
                "info",
                "https://kns.cnki.net/example",
                "--title",
                "文章",
            ]
        )


def test_tool_info_url_rejects_citation_options() -> None:
    """Direct URL parsing does not silently ignore citation fields."""
    with pytest.raises(SystemExit):
        main(
            [
                "tool",
                "info",
                "https://kns.cnki.net/example",
                "--author",
                "张三",
            ]
        )


@patch("cnki_mcp.cli.main.CnkiClient")
def test_login_and_logout_accept_profile(mock_client_cls: MagicMock) -> None:
    """Profile selection remains available for login and logout."""
    client = mock_client_cls.return_value
    client.login.return_value = LoginResult(
        success=True,
        message="ok",
        auth_state=AuthState(is_logged_in=True, profile="school"),
    )
    client.current_profile = "school"

    assert main(["login", "--profile", "school"]) == 0
    mock_client_cls.assert_called_with(profile="school")
    client.login.assert_called_once()

    assert main(["logout", "--profile", "school"]) == 0
    client.logout.assert_called_once()


@patch("cnki_mcp.cli.main.CnkiClient")
def test_cnki_error_returns_nonzero(mock_client_cls: MagicMock) -> None:
    """CNKI errors produce a non-zero command exit code."""
    client = mock_client_cls.return_value
    client.search_basic.side_effect = CnkiMcpError("boom")

    assert main(["tool", "search", "query"]) != 0
