#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/tools/search.py

"""Professional-search entry point for CNKI."""

import re
from collections.abc import Iterable

from ..exceptions import SearchError
from ..models import SearchFilters, SearchResult
from ..ratelimit import rate_limited
from ..retrieval.models import CnkiQuery
from . import professional_search

PROFESSIONAL_EXPRESSION_PATTERN = re.compile(
    r"(?:^|[\s(])(?:SU|TKA|KY|TI|FT|AU|FI|RP|AF|FU|AB|CO|RF|CLC|LY|DOI|CF)\s*(?:=|%)",
    flags=re.IGNORECASE,
)
DEFAULT_FILTER_PRODUCTS = (
    "CJFQ,CAPJ,ZHYX,CJTL,CDFD,CMFD,WBFD,WBFD_SECTION,CPFD,IPFD,CCND,"
    "SCSF,SCHF,SCSD,SNAD,CCJD,CCVD,CJFN"
)

DOCUMENT_TYPE_ALIASES = {
    "journal": "学术期刊",
    "journals": "学术期刊",
    "academicjournal": "学术期刊",
    "academicjournals": "学术期刊",
    "期刊": "学术期刊",
    "学术期刊": "学术期刊",
    "dissertation": "学位论文",
    "thesis": "学位论文",
    "degreepaper": "学位论文",
    "学位论文": "学位论文",
    "conference": "会议",
    "conferencepaper": "会议",
    "会议": "会议",
    "newspaper": "报纸",
    "报纸": "报纸",
    "book": "图书",
    "图书": "图书",
    "yearbook": "年鉴",
    "年鉴": "年鉴",
    "patent": "专利",
    "专利": "专利",
    "standard": "标准",
    "标准": "标准",
    "law": "法律法规",
    "laws": "法律法规",
    "法律法规": "法律法规",
}

SOURCE_TYPE_ALIASES = {
    "core": ("P01", "北大核心"),
    "pkucore": ("P01", "北大核心"),
    "beidacore": ("P01", "北大核心"),
    "北大核心": ("P01", "北大核心"),
    "cssci": ("P0209", "CSSCI"),
    "ami": ("P13", "AMI"),
    "cscd": ("P0210", "CSCD"),
    "wjci": ("P12", "WJCI"),
    "ei": ("P0202", "EI"),
    "sci": ("P0201", "SCI"),
}


def _normalize_key(value: str) -> str:
    """Normalize an alias key for dictionary lookup."""
    return "".join(char for char in value.lower() if char not in {" ", "_", "-"})


def _clean_text(value: str | None) -> str | None:
    """Normalize optional user-provided text values."""
    if value is None:
        return None
    text = " ".join(value.split())
    return text or None


def _normalize_string_list(values: Iterable[str] | str | None) -> list[str]:
    """Normalize a string or iterable into a clean list."""
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    return [text for value in values if (text := _clean_text(value))]


def _normalize_filters(
    filters: SearchFilters | None = None,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
    journal: str | None = None,
    document_type: str | None = None,
    source_types: Iterable[str] | str | None = None,
    author: str | None = None,
    institution: str | None = None,
) -> SearchFilters:
    """Merge explicit filter arguments into one SearchFilters value."""
    filters = filters or SearchFilters()
    return SearchFilters(
        year_from=year_from if year_from is not None else filters.year_from,
        year_to=year_to if year_to is not None else filters.year_to,
        journal=_clean_text(journal) or filters.journal,
        document_type=_clean_text(document_type) or filters.document_type,
        source_types=_normalize_string_list(source_types) or list(filters.source_types),
        author=_clean_text(author) or filters.author,
        institution=_clean_text(institution) or filters.institution,
    )


def _normalize_document_type(document_type: str | None) -> str | None:
    """Return the CNKI resource-type label used by the result page."""
    text = _clean_text(document_type)
    if text is None:
        return None
    return DOCUMENT_TYPE_ALIASES.get(_normalize_key(text), text)


def _normalize_source_type(source_type: str) -> tuple[str, str]:
    """Return a CNKI source-category code and display title."""
    text = source_type.strip()
    alias = SOURCE_TYPE_ALIASES.get(_normalize_key(text))
    if alias is not None:
        return alias
    if text.upper().startswith("P"):
        return text, text
    supported = ", ".join(sorted({title for _, title in SOURCE_TYPE_ALIASES.values()}))
    raise SearchError(
        f"unsupported source type {source_type!r}; supported: {supported}"
    )


def _build_source_type_filter(filters: SearchFilters) -> dict[str, object] | None:
    """Build the CNKI source-category result filter."""
    if not filters.source_types:
        return None
    items = []
    for source_type in filters.source_types:
        code, title = _normalize_source_type(source_type)
        items.append(
            {
                "Key": code,
                "Title": title,
                "Logic": 1,
                "Field": "LYBSM",
                "Operator": "DEFAULT",
                "Value": code,
                "Value2": "",
                "Name": "LYBSM",
                "ExtendType": 0,
            }
        )
    return {"key": "LYBSM", "items": items}


def _build_filter_payload(filters: SearchFilters) -> dict[str, object]:
    """Build post-search filters used on the professional result page."""
    source_filter = _build_source_type_filter(filters)
    return {
        "documentType": _normalize_document_type(filters.document_type),
        "groupFilters": [source_filter] if source_filter is not None else [],
        "defaultFilterProducts": DEFAULT_FILTER_PRODUCTS,
    }


def _normalize_year_range(filters: SearchFilters) -> tuple[int | None, int | None]:
    """Validate and complete optional publication-year bounds."""
    if filters.year_from is None and filters.year_to is None:
        return None, None
    start = filters.year_from if filters.year_from is not None else filters.year_to
    end = filters.year_to if filters.year_to is not None else filters.year_from
    if start is not None and end is not None and end < start:
        raise SearchError("year_to must be greater than or equal to year_from")
    return start, end


@rate_limited(profile=None)
def run(
    query: str | CnkiQuery,
    *,
    profile: str | None = None,
    limit: int = 10,
    max_pages: int = 1,
    filters: SearchFilters | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    journal: str | None = None,
    document_type: str | None = None,
    source_types: Iterable[str] | str | None = None,
    author: str | None = None,
    institution: str | None = None,
    sort_by: str | None = None,
) -> list[SearchResult]:
    """Run every CNKI search through the professional-search page.

    ``query`` may be a professional expression using these fields:
    SU=主题, TKA=篇关摘, KY=关键词, TI=篇名, FT=全文, AU=作者,
    FI=第一作者, RP=通讯作者, AF=作者单位, FU=基金, AB=摘要,
    CO=小标题, RF=参考文献, CLC=分类号, LY=文献来源, DOI=DOI,
    CF=被引频次.

    A plain string is treated as an exact ``TI`` value. All optional filters,
    including year ranges, institutions, document types, and source categories,
    remain within the professional-search workflow.
    """
    search_filters = _normalize_filters(
        filters,
        year_from=year_from,
        year_to=year_to,
        journal=journal,
        document_type=document_type,
        source_types=source_types,
        author=author,
        institution=institution,
    )
    start_year, end_year = _normalize_year_range(search_filters)
    filter_payload = _build_filter_payload(search_filters)

    if isinstance(query, CnkiQuery):
        return professional_search._run(
            query,
            profile=profile,
            limit=limit,
            max_pages=max_pages,
            year_from=start_year,
            year_to=end_year,
            filter_payload=filter_payload,
            sort_by=sort_by,
        )[:limit]

    is_expression = bool(PROFESSIONAL_EXPRESSION_PATTERN.search(query))
    expression = professional_search.build_filtered_expression(
        query,
        title_is_literal=not is_expression,
        source=search_filters.journal,
        author=search_filters.author,
        institution=search_filters.institution,
    )
    return professional_search._run_expression(
        expression,
        year_from=start_year,
        year_to=end_year,
        filter_payload=filter_payload,
        sort_by=sort_by,
        profile=profile,
        limit=limit,
        max_pages=max_pages,
    )[:limit]


__all__ = ["run"]
