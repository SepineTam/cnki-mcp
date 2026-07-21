#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/server/test_cnki_mcp_server.py

"""Tests for transport-specific MCP server registration and lifecycle."""

import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Any

from cnki_mcp.server.cnki_mcp_server import create_mcp_server

BASE_TOOL_NAMES = {
    "easy-search",
    "advanced-search",
    "get-info-from-url",
    "get-info-by-detail",
}


class FakeService:
    """Record server lifecycle calls without opening a real browser."""

    def __init__(self) -> None:
        """Initialize lifecycle counters."""
        self.network_start_count = 0
        self.close_count = 0

    def start_network(self) -> None:
        """Record network browser startup."""
        self.network_start_count += 1

    def close(self) -> None:
        """Record service shutdown."""
        self.close_count += 1

    def easy_search(
        self,
        keywords: str,
        limit: int = 10,
        sort_by: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return an empty easy-search result."""
        return []

    def advanced_search(
        self,
        title: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return an empty advanced-search result."""
        return []

    def get_info_from_url(self, url: str) -> dict[str, Any]:
        """Return a minimal URL metadata result."""
        return {"url": url}

    def get_info_by_detail(self, title: str) -> list[dict[str, Any]]:
        """Return an empty detailed lookup result."""
        return []

    def login(self, profile: str | None = None) -> dict[str, Any]:
        """Return a minimal login result."""
        return {"success": True, "profile": profile}

    def logout(self) -> dict[str, Any]:
        """Return a minimal logout result."""
        return {"success": True}

    def list_profiles(self) -> dict[str, Any]:
        """Return a minimal profile resource."""
        return {"default": "default", "profiles": ["default"]}

    def refresh_browser(self) -> dict[str, Any]:
        """Expose a stub that must never be registered."""
        return {"success": False, "error": "not implemented"}


def _tool_names(server: Any) -> set[str]:
    """Return registered MCP tool names."""
    return {tool.name for tool in asyncio.run(server.list_tools())}


def _tools_by_name(server: Any) -> dict[str, Any]:
    """Return registered MCP tools keyed by public name."""
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


def _resource_uris(server: Any) -> set[str]:
    """Return registered static MCP resource URIs."""
    return {str(resource.uri) for resource in asyncio.run(server.list_resources())}


def _lifespan(server: Any) -> AbstractAsyncContextManager[Any]:
    """Build the configured FastMCP lifespan context."""
    lifespan = server.settings.lifespan
    assert lifespan is not None
    return lifespan(server)


async def _enter_lifespan(server: Any) -> None:
    """Enter and leave a server lifespan once."""
    async with _lifespan(server):
        return


def test_http_registers_only_four_public_tools() -> None:
    """HTTP exposes search and info tools only."""
    server = create_mcp_server("http")

    assert _tool_names(server) == BASE_TOOL_NAMES
    assert _resource_uris(server) == set()


def test_sse_registers_only_four_public_tools() -> None:
    """SSE has the same public surface as HTTP."""
    server = create_mcp_server("sse", service=FakeService())

    assert _tool_names(server) == BASE_TOOL_NAMES
    assert _resource_uris(server) == set()


def test_stdio_adds_login_logout_and_profile_resource() -> None:
    """stdio adds local browser controls and profile discovery."""
    server = create_mcp_server("stdio", service=FakeService())

    assert _tool_names(server) == BASE_TOOL_NAMES | {"login", "logout"}
    assert _resource_uris(server) == {"profile://list"}


def test_refresh_browser_is_not_registered_for_any_transport() -> None:
    """The recovery stub remains internal until it is implemented."""
    for transport in ("http", "sse", "stdio"):
        server = create_mcp_server(transport, service=FakeService())

        assert "refresh-browser" not in _tool_names(server)


def test_advanced_search_description_explains_professional_fields() -> None:
    """The expanded tool teaches clients how its fields map to CNKI."""
    server = create_mcp_server("http")
    tool = _tools_by_name(server)["advanced-search"]
    description = tool.description or ""

    assert "SU=主题" in description
    assert "TI=篇名" in description
    assert "AU=作者" in description


def test_advanced_search_does_not_publish_negative_parameter() -> None:
    """The explicitly deferred negative condition stays out of the schema."""
    server = create_mcp_server("http")
    tool = _tools_by_name(server)["advanced-search"]

    assert "negative" not in tool.inputSchema.get("properties", {})


def test_url_info_description_mentions_search_cache_window() -> None:
    """Clients are told where URLs come from and when they are reliable."""
    server = create_mcp_server("http")
    tool = _tools_by_name(server)["get-info-from-url"]
    description = (tool.description or "").lower()

    assert "easy-search" in description
    assert "advanced-search" in description
    assert "ten minutes" in description


def test_network_lifecycle_starts_browser_and_closes_service() -> None:
    """HTTP and SSE own one browser for the complete process lifetime."""
    for transport in ("http", "sse"):
        service = FakeService()
        server = create_mcp_server(transport, service=service)

        asyncio.run(_enter_lifespan(server))

        assert service.network_start_count == 1
        assert service.close_count == 1


def test_stdio_lifecycle_does_not_start_browser() -> None:
    """stdio waits for the explicit login tool before opening a browser."""
    service = FakeService()
    server = create_mcp_server("stdio", service=service)

    asyncio.run(_enter_lifespan(server))

    assert service.network_start_count == 0
    assert service.close_count == 1


def test_server_uses_requested_network_address() -> None:
    """Factory forwards host and port to FastMCP settings."""
    server = create_mcp_server(
        "http",
        host="127.0.0.2",
        port=7789,
        service=FakeService(),
    )

    assert server.settings.host == "127.0.0.2"
    assert server.settings.port == 7789


def test_server_rejects_unknown_transport() -> None:
    """Invalid transport values fail before any browser is opened."""
    try:
        create_mcp_server("websocket", service=FakeService())
    except ValueError as exc:
        assert "transport" in str(exc).lower()
    else:
        raise AssertionError("unknown transport must be rejected")
