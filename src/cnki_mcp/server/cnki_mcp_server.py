#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : server/cnki_mcp_server.py

"""FastMCP server exposing CNKI search and metadata tools."""

from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..core.client import CnkiClient
from ..core.exceptions import CnkiMcpError
from ..core.models import Article, SearchResult
from ..core.retrieval.models import MetadataLookupResult


def _to_dict(
    obj: SearchResult | Article | MetadataLookupResult,
) -> dict[str, Any]:
    """Convert a model instance to a JSON-serializable dictionary.

    Args:
        obj: SearchResult or Article instance.

    Returns:
        Dictionary representation of the model.
    """
    raw_data = asdict(obj) if is_dataclass(obj) else obj.__dict__
    data: dict[str, Any] = {}
    for key, value in raw_data.items():
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
    sort_by: str | None = None,
    profile: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    journal: str | None = None,
    document_type: str | None = None,
    source_types: list[str] | None = None,
    author: str | None = None,
    institution: str | None = None,
) -> list[dict[str, Any]]:
    """Search CNKI and return compact citation records.

    专业检索字段：
    SU=主题, TKA=篇关摘, KY=关键词, TI=篇名, FT=全文, AU=作者,
    FI=第一作者, RP=通讯作者, AF=作者单位, FU=基金, AB=摘要,
    CO=小标题, RF=参考文献, CLC=分类号, LY=文献来源, DOI=DOI,
    CF=被引频次。

    示例：
    1. ``TI='生态' and KY='生态文明' and (AU % '陈' + '王')``
       检索篇名包括“生态”、关键词包括“生态文明”，且作者为“陈”姓或
       “王”姓的文章。
    2. ``SU='北京' * '奥运' and FT='环境保护'``
       检索主题同时包括“北京”和“奥运”，且全文包括“环境保护”的信息。
    3. ``SU=('经济发展' + '可持续发展') * '转变' - '泡沫'``
       检索相关“转变”信息，并排除“泡沫”。

    Args:
        query: Professional expression or a plain article title.
        limit: Maximum number of results to return.
        sort_by: Result order: relevance, date, citation, or comprehensive.
        profile: Optional profile name.
        year_from: Optional start publication year.
        year_to: Optional end publication year.
        journal: Optional journal or source title.
        document_type: Optional resource type, for example ``journal``.
        source_types: Optional source categories such as ``CSSCI`` or ``SCI``.
        author: Optional author filter.
        institution: Optional author institution filter.

    Returns:
        Records containing only ``title``, ``authors``, ``journal``, and
        ``date``. Use a metadata tool when detailed fields are needed.
    """
    try:
        with CnkiClient(profile=profile) as client:
            results = client.search(
                query,
                limit=limit,
                sort_by=sort_by,
                year_from=year_from,
                year_to=year_to,
                journal=journal,
                document_type=document_type,
                source_types=source_types,
                author=author,
                institution=institution,
            )
            return [result.to_public_dict() for result in results]
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
def cnki_lookup_metadata(
    title: str,
    authors: list[str] | None = None,
    year: int | None = None,
    source: str | None = None,
    document_type: str | None = None,
    limit: int = 10,
    profile: str | None = None,
) -> dict[str, Any]:
    """Resolve CNKI metadata from known citation fields.

    Args:
        title: Article title.
        authors: Optional complete author list.
        year: Optional publication year.
        source: Optional source or journal title.
        document_type: Optional document type.
        limit: Maximum number of search candidates.
        profile: Optional profile name.

    Returns:
        Lookup result with the selected article and ranked candidates.
    """
    try:
        with CnkiClient(profile=profile) as client:
            result = client.lookup_metadata(
                title,
                authors=authors,
                year=year,
                source=source,
                document_type=document_type,
                limit=limit,
            )
            return _to_dict(result)
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
