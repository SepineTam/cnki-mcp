#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : server/cnki_mcp_server.py

"""Build FastMCP servers with transport-specific CNKI capabilities."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from .tool_registry import McpToolService

NETWORK_TRANSPORTS = {"http", "sse"}
SUPPORTED_TRANSPORTS = NETWORK_TRANSPORTS | {"stdio"}


def _register_search_and_info_tools(
    server: FastMCP[Any],
    service: McpToolService,
) -> None:
    """Register the tools shared by every transport."""
    server.tool(name="easy-search")(service.easy_search)
    server.tool(name="advanced-search")(service.advanced_search)
    server.tool(name="get-info-from-url")(service.get_info_from_url)
    server.tool(name="get-info-by-detail")(service.get_info_by_detail)
    server.tool(name="list-journal")(service.list_journal)
    server.tool(name="search-issn")(service.search_issn)


def _register_stdio_capabilities(
    server: FastMCP[Any],
    service: McpToolService,
) -> None:
    """Register browser controls and profile discovery for stdio."""
    server.tool(name="login")(service.login)
    server.tool(name="logout")(service.logout)
    server.resource(
        "profile://list",
        name="list-profiles",
        description="List profiles that can be passed to the login tool.",
    )(service.list_profiles)


def create_mcp_server(
    transport: str,
    *,
    host: str = "127.0.0.1",
    port: int = 7788,
    service: McpToolService | None = None,
) -> FastMCP[Any]:
    """Create one MCP server for HTTP, SSE, or stdio."""
    if transport not in SUPPORTED_TRANSPORTS:
        supported = ", ".join(sorted(SUPPORTED_TRANSPORTS))
        raise ValueError(f"unsupported transport {transport!r}; supported: {supported}")

    tool_service = service or McpToolService()

    @asynccontextmanager
    async def lifespan(_: FastMCP[Any]) -> AsyncIterator[None]:
        if transport in NETWORK_TRANSPORTS:
            await asyncio.to_thread(tool_service.start_network)
        try:
            yield
        finally:
            close_service = (
                tool_service.close_network
                if transport in NETWORK_TRANSPORTS
                else tool_service.close
            )
            await asyncio.to_thread(close_service)

    server = FastMCP(
        name="cnki-mcp",
        instructions=(
            "Search CNKI and retrieve article metadata. HTTP is the recommended "
            "transport. Full-text downloading is not provided."
        ),
        host=host,
        port=port,
        lifespan=lifespan,
    )
    if host not in {"127.0.0.1", "localhost", "::1"}:
        server.settings.transport_security = None
    _register_search_and_info_tools(server, tool_service)
    if transport == "stdio":
        _register_stdio_capabilities(server, tool_service)
    return server


__all__ = ["create_mcp_server"]
