#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : server/cnki_mcp_server.py

"""FastMCP server exposing CNKI search and metadata tools."""

from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..core.client import CnkiClient
from ..core.exceptions import CnkiMcpError
from ..core.models import Article, SearchResult


def _to_dict(obj: SearchResult | Article) -> dict[str, Any]:
    """Convert a model instance to a JSON-serializable dictionary.

    Args:
        obj: SearchResult or Article instance.

    Returns:
        Dictionary representation of the model.
    """
    data: dict[str, Any] = {}
    for key, value in obj.__dict__.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, Path):
            data[key] = str(value)
        else:
            data[key] = value
    return data


mcp_server = FastMCP()


@mcp_server.tool()
def cnki_search(
    query: str,
    limit: int = 10,
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """Search CNKI and return a list of result dictionaries.

    Args:
        query: Search query string.
        limit: Maximum number of results to return.
        profile: Optional profile name.

    Returns:
        List of search result dictionaries.
    """
    try:
        with CnkiClient(profile=profile) as client:
            results = client.search(query, limit=limit)
            return [_to_dict(r) for r in results]
    except CnkiMcpError as exc:
        return [{"success": False, "error": str(exc)}]


@mcp_server.tool()
def cnki_get_metadata(
    article_id: str,
    profile: str | None = None,
) -> dict[str, Any]:
    """Fetch CNKI article metadata.

    Args:
        article_id: Article identifier.
        profile: Optional profile name.

    Returns:
        Article metadata dictionary.
    """
    try:
        with CnkiClient(profile=profile) as client:
            return _to_dict(client.get_metadata(article_id))
    except CnkiMcpError as exc:
        return {"success": False, "error": str(exc)}


@mcp_server.tool()
def cnki_login(profile: str | None = None) -> dict[str, Any]:
    """Log in to CNKI via an interactive browser flow.

    Args:
        profile: Optional profile name.

    Returns:
        Login result dictionary.
    """
    try:
        with CnkiClient(profile=profile) as client:
            result = client.login()
            return {
                "success": result.success,
                "message": result.message,
                "profile": result.auth_state.profile,
            }
    except CnkiMcpError as exc:
        return {"success": False, "error": str(exc)}


@mcp_server.tool()
def cnki_logout(profile: str | None = None) -> dict[str, Any]:
    """Log out from CNKI for the given profile.

    Args:
        profile: Optional profile name.

    Returns:
        Logout result dictionary.
    """
    try:
        with CnkiClient(profile=profile) as client:
            client.logout()
            return {"success": True, "profile": client.current_profile}
    except CnkiMcpError as exc:
        return {"success": False, "error": str(exc)}


__all__ = ["mcp_server"]
