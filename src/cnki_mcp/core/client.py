#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/client.py

"""High-level CNKI client facade."""

from typing import Any

from .auth import (
    ensure_login,
    get_default_profile,
    login,
    logout,
    refresh_login,
)
from .config import AUTH_TIMEOUT_SECONDS
from .models import Article, AuthState, LoginResult, SearchFilters, SearchResult
from .retrieval.models import CnkiQuery, MetadataLookupResult
from .tools import basic_search, metadata, metadata_lookup, search


class CnkiClient:
    """High-level client for CNKI search and metadata operations."""

    def __init__(self, profile: str | None = None) -> None:
        """Initialize the client bound to a profile.

        Args:
            profile: Optional profile name; defaults to the current default.
        """
        self._profile = profile if profile is not None else get_default_profile()

    @property
    def current_profile(self) -> str:
        """Return the resolved profile name."""
        return self._profile

    def _ensure_login(
        self,
        headless: bool = False,
        timeout: int = AUTH_TIMEOUT_SECONDS,
    ) -> AuthState:
        """Ensure the profile is logged in."""
        return ensure_login(profile=self._profile, headless=headless, timeout=timeout)

    def login(
        self,
        headless: bool = False,
        timeout: int = AUTH_TIMEOUT_SECONDS,
    ) -> LoginResult:
        """Trigger an interactive login flow for the profile."""
        return login(profile=self._profile, headless=headless, timeout=timeout)

    def logout(self) -> None:
        """Clear the profile authentication state."""
        logout(profile=self._profile)

    def refresh_login(
        self,
        headless: bool = False,
        timeout: int = AUTH_TIMEOUT_SECONDS,
    ) -> LoginResult:
        """Clear and refresh the profile login state."""
        return refresh_login(
            profile=self._profile,
            headless=headless,
            timeout=timeout,
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        sort_by: str | None = None,
        filters: SearchFilters | None = None,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """Search CNKI and return parsed results.

        Professional fields:
        SU=主题, TKA=篇关摘, KY=关键词, TI=篇名, FT=全文, AU=作者,
        FI=第一作者, RP=通讯作者, AF=作者单位, FU=基金, AB=摘要,
        CO=小标题, RF=参考文献, CLC=分类号, LY=文献来源, DOI=DOI,
        CF=被引频次.

        Examples:
            ``TI='生态' and KY='生态文明' and (AU % '陈' + '王')``
            检索篇名包括“生态”、关键词包括“生态文明”，且作者为“陈”姓或
            “王”姓的文章。

            ``SU='北京' * '奥运' and FT='环境保护'``
            检索主题同时包括“北京”和“奥运”，且全文包括“环境保护”的信息。

            ``SU=('经济发展' + '可持续发展') * '转变' - '泡沫'``
            检索相关“转变”信息，并排除“泡沫”。

        Args:
            query: Professional expression or a plain article title.
            limit: Maximum number of results to return.
            sort_by: Result order: relevance, date, citation, or comprehensive.
            filters: Optional grouped search filters.
            **kwargs: Additional search options forwarded to the search tool.

        Returns:
            Search results whose public fields are title, authors, journal,
            and publication date.
        """
        self._ensure_login()
        return search.run(
            query,
            profile=self._profile,
            limit=limit,
            sort_by=sort_by,
            filters=filters,
            **kwargs,
        )

    def get_metadata(self, article_id: str) -> Article:
        """Fetch metadata for a CNKI article.

        Args:
            article_id: Article identifier.

        Returns:
            Parsed article metadata.
        """
        self._ensure_login()
        return metadata.run(article_id, profile=self._profile)

    def search_basic(
        self,
        query: str,
        *,
        limit: int = 10,
        sort_by: str | None = None,
        filters: SearchFilters | None = None,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """Search CNKI through the one-box search page."""
        self._ensure_login()
        return basic_search.run(
            query,
            profile=self._profile,
            limit=limit,
            sort_by=sort_by,
            filters=filters,
            **kwargs,
        )

    def lookup_metadata(
        self,
        title: str,
        *,
        authors: list[str] | None = None,
        year: int | None = None,
        source: str | None = None,
        document_type: str | None = None,
        limit: int = 10,
    ) -> MetadataLookupResult:
        """Resolve complete metadata from known citation fields.

        Args:
            title: Article title.
            authors: Optional complete author list.
            year: Optional publication year.
            source: Optional source or journal title.
            document_type: Optional document type.
            limit: Maximum number of search candidates.

        Returns:
            Lookup result with the selected article and ranked candidates.
        """
        self._ensure_login()
        query = CnkiQuery(
            title=title,
            authors=list(authors or []),
            year=year,
            source=source,
            document_type=document_type,
        )
        return metadata_lookup.lookup(
            query,
            profile=self._profile,
            limit=limit,
        )

    def __enter__(self) -> "CnkiClient":
        """Enter the client context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the client context manager."""
        pass


__all__ = ["CnkiClient"]
