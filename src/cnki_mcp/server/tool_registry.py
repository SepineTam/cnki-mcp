#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : server/tool_registry.py

"""Transport-independent implementation of CNKI MCP tools."""

from dataclasses import asdict
from typing import Any

from ..core import auth
from ..core.browser_worker import BrowserWorker
from ..core.models import SearchFilters, SearchResult
from ..core.retrieval.models import CnkiQuery
from ..core.tools import basic_search, metadata, professional_search, search
from .search_cache import SearchResultCache


def _search_result_to_dict(result: SearchResult) -> dict[str, Any]:
    """Return the compact MCP search shape including its detail URL."""
    return {
        "title": result.title,
        "authors": list(result.authors),
        "journal": result.journal,
        "date": result.date,
        "url": result.url or result.article_id,
    }


class McpToolService:
    """Own one browser worker and implement all MCP-facing operations."""

    def __init__(
        self,
        *,
        worker: BrowserWorker | None = None,
        cache: SearchResultCache | None = None,
    ) -> None:
        """Initialize a service without starting its browser."""
        self.worker = worker if worker is not None else BrowserWorker()
        self.cache = cache if cache is not None else SearchResultCache()

    def start_network(self) -> None:
        """Ensure login and start the browser used by a network server."""
        auth.ensure_login(profile=None)
        self.worker.start(profile=None)

    def close(self) -> None:
        """Close the browser while preserving persisted login state."""
        self.worker.close()
        self.cache.clear()

    def easy_search(
        self,
        keywords: str,
        limit: int = 10,
        sort_by: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search CNKI's one-box interface and return compact result records."""
        results = self.worker.call(
            lambda page: basic_search.run_on_page(
                page,
                keywords,
                limit=limit,
                max_pages=_page_count(limit),
                sort_by=sort_by,
            )
        )
        return self._store_search_results(results)

    def advanced_search(
        self,
        title: str | None = None,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        journal: str | None = None,
        keywords: str | None = None,
        subject: str | None = None,
        abstract: str | None = None,
        institution: str | None = None,
        fund: str | None = None,
        doi: str | None = None,
        document_type: str | None = None,
        source_types: list[str] | None = None,
        sort_by: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search CNKI by structured professional-search fields.

        专业检索字段：SU=主题, TKA=篇关摘, KY=关键词, TI=篇名,
        FT=全文, AU=作者, FI=第一作者, RP=通讯作者, AF=作者单位,
        FU=基金, AB=摘要, CO=小标题, RF=参考文献, CLC=分类号,
        LY=文献来源, DOI=DOI, CF=被引频次。
        """
        expression = professional_search.build_structured_expression(
            title=title,
            author=author,
            journal=journal,
            keywords=keywords,
            subject=subject,
            abstract=abstract,
            institution=institution,
            fund=fund,
            doi=doi,
        )
        filters = SearchFilters(
            document_type=document_type,
            source_types=source_types or [],
        )
        filter_payload = search._build_filter_payload(filters)
        results = self.worker.call(
            lambda page: professional_search.run_expression_on_page(
                page,
                expression,
                year_from=year_from,
                year_to=year_to,
                filter_payload=filter_payload,
                sort_by=sort_by,
                limit=limit,
                max_pages=_page_count(limit),
            )
        )
        return self._store_search_results(results)

    def get_info_from_url(self, url: str) -> dict[str, Any]:
        """Get article info from a URL returned by search.

        The URL should come from ``easy-search`` or ``advanced-search``.
        Search results are retained for ten minutes. Retrieval is most reliable
        during that window; an older URL is still attempted without a guarantee.
        """
        cached = self.cache.get(url)
        target = url
        if cached is not None:
            target = cached.url or cached.article_id
        article = self.worker.call(lambda page: metadata.run_on_page(page, target))
        return asdict(article)

    def get_info_by_detail(
        self,
        title: str,
        authors: list[str] | None = None,
        year: int | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        journal: str | None = None,
        keywords: str | None = None,
        subject: str | None = None,
        abstract: str | None = None,
        institution: str | None = None,
        fund: str | None = None,
        doi: str | None = None,
        document_type: str | None = None,
        source_types: list[str] | None = None,
        sort_by: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Locate articles by detailed fields and return info for every match."""
        query = CnkiQuery(
            title=title,
            authors=authors or [],
            year=year,
            source=journal,
            document_type=document_type,
        )
        expression = professional_search.build_expression(query)
        extra_expression = professional_search.build_structured_expression(
            keywords=keywords,
            subject=subject,
            abstract=abstract,
            institution=institution,
            fund=fund,
            doi=doi,
        ) if any((keywords, subject, abstract, institution, fund, doi)) else None
        if extra_expression:
            expression = f"({expression}) and ({extra_expression})"

        start_year = year_from if year_from is not None else year
        end_year = year_to if year_to is not None else year
        filters = SearchFilters(
            document_type=document_type,
            source_types=source_types or [],
        )
        results = self.worker.call(
            lambda page: professional_search.run_expression_on_page(
                page,
                expression,
                year_from=start_year,
                year_to=end_year,
                filter_payload=search._build_filter_payload(filters),
                sort_by=sort_by,
                limit=limit,
                max_pages=_page_count(limit),
            )
        )
        self.cache.put(results)
        records: list[dict[str, Any]] = []
        for result in results:
            target = result.url or result.article_id
            try:
                article = self.worker.call(
                    lambda page, value=target: metadata.run_on_page(page, value)
                )
                records.append(asdict(article))
            except Exception as exc:
                records.append(
                    {
                        "success": False,
                        "error": str(exc),
                        "title": result.title,
                        "url": target,
                    }
                )
        return records

    def login(self, profile: str | None = None) -> dict[str, Any]:
        """Log in or select a profile, then start its persistent browser."""
        resolved_profile = profile or auth.get_default_profile()
        if (
            self.worker.is_running
            and self.worker.current_profile == resolved_profile
        ):
            return {"success": True, "profile": resolved_profile}
        state = auth.ensure_login(profile=resolved_profile)
        self.worker.start(profile=state.profile)
        return {"success": True, "profile": state.profile}

    def logout(self) -> dict[str, Any]:
        """Close the stdio browser without deleting persisted login state."""
        profile = self.worker.current_profile
        self.worker.close()
        self.cache.clear()
        return {"success": True, "profile": profile}

    def list_profiles(self) -> dict[str, Any]:
        """List profiles available to the stdio login tool."""
        return {
            "default_profile": auth.get_default_profile(),
            "profiles": auth.list_profiles(),
        }

    def refresh_browser(self) -> dict[str, bool | str]:
        """Return the unregistered browser-refresh placeholder."""
        return self.worker.refresh_browser()

    def _store_search_results(
        self,
        results: list[SearchResult],
    ) -> list[dict[str, Any]]:
        """Cache and serialize compact search results."""
        self.cache.put(results)
        return [_search_result_to_dict(result) for result in results]


def _page_count(limit: int) -> int:
    """Estimate enough result pages for the requested limit."""
    return max(1, (limit + 19) // 20)


__all__ = ["McpToolService"]
