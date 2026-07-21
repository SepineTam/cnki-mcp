#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/tools/professional_search.py

"""Atomic professional-search operation for CNKI."""

import re
from typing import Any

from ..auth import ensure_login
from ..config import PAGE_LOAD_TIMEOUT_SECONDS
from ..exceptions import ParseError, SearchError
from ..models import SearchResult
from ..parsers.search_parser import parse
from ..ratelimit import rate_limited
from ..retrieval.models import CnkiQuery
from ..runtime import Runtime

CNKI_PROFESSIONAL_SEARCH_URL = (
    "https://kns.cnki.net/kns8s/AdvSearch?type=expert"
)
SECURITY_VERIFICATION_TEXT = "请完成安全验证"
SORT_BY_ALIASES = {
    "relevance": "FFD",
    "相关度": "FFD",
    "date": "PT",
    "publication_date": "PT",
    "发表时间": "PT",
    "citation": "CF",
    "citations": "CF",
    "被引": "CF",
    "comprehensive": "ZH",
    "综合": "ZH",
}
PROFESSIONAL_SEARCH_GUIDE = """专业检索式字段：
SU=主题, TKA=篇关摘, KY=关键词, TI=篇名, FT=全文, AU=作者,
FI=第一作者, RP=通讯作者, AF=作者单位, FU=基金, AB=摘要,
CO=小标题, RF=参考文献, CLC=分类号, LY=文献来源, DOI=DOI,
CF=被引频次。

示例：
1. TI='生态' and KY='生态文明' and (AU % '陈' + '王')
   检索篇名包括“生态”、关键词包括“生态文明”，且作者为“陈”姓或“王”姓的文章。
2. SU='北京' * '奥运' and FT='环境保护'
   检索主题同时包括“北京”和“奥运”，且全文包括“环境保护”的信息。
3. SU=('经济发展' + '可持续发展') * '转变' - '泡沫'
   检索与“经济发展”或“可持续发展”有关的“转变”信息，并排除“泡沫”。
"""

APPLY_RESULT_FILTERS_SCRIPT = """(payload) => {
    const normalize = (value) => String(value || "")
        .replace(/[\\s_-]+/g, "")
        .toLowerCase();
    const clickDocumentType = () => {
        if (!payload.documentType) return false;
        const links = Array.from(
            document.querySelectorAll("a[data-chs], .doctype-menus a")
        );
        const target = normalize(payload.documentType);
        const link = links.find((item) => normalize(item.innerText).includes(target));
        if (!link) {
            throw new Error(`document type not found: ${payload.documentType}`);
        }
        link.click();
        return true;
    };
    const applyGroups = () => {
        if (!payload.groupFilters.length) return;
        if (typeof cnkiSearch === "undefined") {
            throw new Error("CNKI search state is unavailable");
        }
        const dbCode = cnkiSearch.getDbCode ? cnkiSearch.getDbCode() : "";
        const kuaKuCode = cnkiSearch.getKuaKuCode ? cnkiSearch.getKuaKuCode() : "";
        const isCrossDb = !dbCode || dbCode === "WD0FTY92" || Boolean(kuaKuCode);
        const groupName = isCrossDb
            ? cnkiSearch.GroupName.SCDBGroup
            : cnkiSearch.GroupName.MutiGroup;
        cnkiSearch.delQueryNode(groupName);
        const rootGroup = cnkiSearch.getRootQueryGroup(groupName);
        rootGroup.Items = [];
        rootGroup.ChildItems = payload.groupFilters.map((group) => ({
            Key: group.key,
            Title: "",
            Logic: 0,
            Items: group.items,
            ChildItems: []
        }));
        if (isCrossDb && payload.defaultFilterProducts && cnkiSearch.setProducts) {
            cnkiSearch.setProducts(payload.defaultFilterProducts);
        }
        BriefExtend.searchCallBackFun(true, 1, SearchFromId.GROUPSEARCH);
        getGroupResult();
    };
    const clicked = clickDocumentType();
    if (clicked && payload.groupFilters.length) {
        return new Promise((resolve) => {
            setTimeout(() => {
                applyGroups();
                resolve({applied: true});
            }, 1500);
        });
    }
    applyGroups();
    return {applied: clicked || payload.groupFilters.length > 0};
}"""

SUBMIT_PROFESSIONAL_SEARCH_SCRIPT = """(payload) => {
    const emitChange = (element) => {
        element.dispatchEvent(new Event("input", {bubbles: true}));
        element.dispatchEvent(new Event("change", {bubbles: true}));
    };
    const clickElement = (element) => {
        element.dispatchEvent(new MouseEvent("mousedown", {bubbles: true}));
        element.dispatchEvent(new MouseEvent("mouseup", {bubbles: true}));
        element.dispatchEvent(new MouseEvent("click", {bubbles: true}));
    };
    const textarea = document.querySelector(
        "textarea.textarea-major.majorSearch, textarea.majorSearch"
    );
    if (!textarea) {
        return {
            submitted: false,
            error: "professional-search textarea unavailable"
        };
    }
    textarea.value = payload.expression;
    emitChange(textarea);
    let yearApplied = false;
    if (payload.yearFrom || payload.yearTo) {
        const dateStart = document.querySelector("#datebox0");
        const dateEnd = document.querySelector("#datebox1");
        if (dateStart && dateEnd) {
            dateStart.value = payload.yearFrom || payload.yearTo;
            dateEnd.value = payload.yearTo || payload.yearFrom;
            emitChange(dateStart);
            emitChange(dateEnd);
            yearApplied = true;
        }
    }
    const button = document.querySelector(".search-buttons .btn-search");
    if (!button) {
        return {
            submitted: false,
            error: "professional-search button unavailable"
        };
    }
    clickElement(button);
    return {submitted: true, yearApplied};
}"""


def _clean_text(value: str | None) -> str | None:
    """Strip an optional text value and discard blanks."""
    if value is None:
        return None
    text = " ".join(value.split())
    return text or None


def _build_clause(field: str, value: str) -> str:
    """Build one equality clause from a trusted field and literal value."""
    if "'" not in value:
        return f"{field}='{value}'"
    if '"' not in value:
        return f'{field}="{value}"'
    raise SearchError("search terms cannot contain both quote types")


def build_structured_expression(
    *,
    title: str | None = None,
    author: str | None = None,
    journal: str | None = None,
    keywords: str | None = None,
    subject: str | None = None,
    abstract: str | None = None,
    institution: str | None = None,
    fund: str | None = None,
    doi: str | None = None,
) -> str:
    """Build a professional expression from public advanced-search fields."""
    fields = (
        ("TI", title),
        ("AU", author),
        ("LY", journal),
        ("KY", keywords),
        ("SU", subject),
        ("AB", abstract),
        ("AF", institution),
        ("FU", fund),
        ("DOI", doi),
    )
    clauses = [
        _build_clause(field, cleaned)
        for field, value in fields
        if (cleaned := _clean_text(value)) is not None
    ]
    if not clauses:
        raise SearchError("at least one advanced-search condition is required")
    return " and ".join(clauses)


def build_filtered_expression(
    expression: str,
    *,
    title_is_literal: bool = False,
    source: str | None = None,
    author: str | None = None,
    institution: str | None = None,
) -> str:
    """Add structured professional clauses to a title or expression."""
    base = _clean_text(expression)
    if base is None:
        raise SearchError("professional search expression is required")
    clauses = [_build_clause("TI", base) if title_is_literal else f"({base})"]
    for field, value in (("LY", source), ("AU", author), ("AF", institution)):
        cleaned = _clean_text(value)
        if cleaned is not None:
            clauses.append(_build_clause(field, cleaned))
    return " and ".join(clauses)


def _build_expression(
    query: CnkiQuery,
    *,
    include_source: bool,
    include_authors: bool,
) -> str:
    """Build one CNKI expression from a selected set of known fields."""
    title = _clean_text(query.title)
    if title is None:
        raise SearchError("title is required for professional search")

    clauses = [_build_clause("TI", title)]
    source = _clean_text(query.source)
    if include_source and source is not None:
        clauses.append(_build_clause("LY", source))
    if include_authors:
        clauses.extend(
            _build_clause("AU", author)
            for author in (_clean_text(value) for value in query.authors)
            if author is not None
        )
    return " and ".join(clauses)


def build_expressions(query: CnkiQuery) -> list[str]:
    """Build unique fallback expressions from broadest to strictest."""
    candidates = [
        _build_expression(query, include_source=False, include_authors=False),
        _build_expression(query, include_source=True, include_authors=False),
        _build_expression(query, include_source=False, include_authors=True),
        _build_expression(query, include_source=True, include_authors=True),
    ]
    return list(dict.fromkeys(candidates))


def build_expression(query: CnkiQuery) -> str:
    """Build the strictest CNKI professional expression for a query."""
    return build_expressions(query)[-1]


def _raise_for_security_verification(page: Any) -> None:
    """Raise a clear error when CNKI blocks the automated request."""
    try:
        title = page.title()
    except Exception:
        title = ""
    try:
        body = page.inner_text("body", timeout=3000)
    except Exception:
        body = ""
    if "安全验证" in title or SECURITY_VERIFICATION_TEXT in body:
        raise SearchError("CNKI requires manual security verification")


def _wait_for_selector(page: Any, selector: str) -> None:
    """Wait for a CNKI page state and report security verification clearly."""
    try:
        page.wait_for_selector(
            selector,
            state="attached",
            timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
        )
    except Exception:
        _raise_for_security_verification(page)
        raise


def _is_empty_result_page(page: Any) -> bool:
    """Return whether CNKI explicitly reports that no records matched."""
    try:
        body = page.inner_text("body", timeout=3000)
    except Exception:
        return False
    if not isinstance(body, str):
        return False
    empty_markers = ("未检索到", "没有找到", "暂无数据", "无检索结果")
    return any(marker in body for marker in empty_markers) or bool(
        re.search(r"共(?:找到|检索到)?\s*0\s*条", body)
    )


def _wait_for_results_or_empty(page: Any) -> None:
    """Wait until CNKI shows either a result table or an explicit empty state."""
    try:
        page.wait_for_selector(
            "#gridTable, .result-table-list, #briefRequest",
            state="attached",
            timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
        )
    except Exception:
        _raise_for_security_verification(page)
        if not _is_empty_result_page(page):
            raise


def _submit(
    page: Any,
    expression: str,
    year_from: int | None = None,
    year_to: int | None = None,
) -> bool:
    """Fill and submit one expression, returning whether year was applied."""
    _wait_for_selector(
        page,
        "textarea.textarea-major.majorSearch, textarea.majorSearch",
    )
    payload = {
        "expression": expression,
        "yearFrom": str(year_from) if year_from is not None else None,
        "yearTo": str(year_to) if year_to is not None else None,
    }
    result = page.evaluate(SUBMIT_PROFESSIONAL_SEARCH_SCRIPT, payload)
    if not isinstance(result, dict) or not result.get("submitted"):
        message = "professional-search form submission failed"
        if isinstance(result, dict) and result.get("error"):
            message = str(result["error"])
        raise SearchError(message)
    page.wait_for_timeout(3000)
    _wait_for_results_or_empty(page)
    return bool(result.get("yearApplied"))


def _apply_result_filters(
    page: Any,
    filter_payload: dict[str, Any] | None,
) -> None:
    """Apply document and source-category filters on professional results."""
    if not filter_payload:
        return
    if not filter_payload.get("documentType") and not filter_payload.get(
        "groupFilters"
    ):
        return
    page.evaluate(APPLY_RESULT_FILTERS_SCRIPT, filter_payload)
    page.wait_for_timeout(3000)
    _wait_for_selector(page, "#gridTable, .result-table-list, #briefRequest")


def _normalize_sort_by(sort_by: str | None) -> str | None:
    """Return a verified CNKI sort code."""
    cleaned = _clean_text(sort_by)
    if cleaned is None:
        return None
    code = SORT_BY_ALIASES.get(cleaned.casefold())
    if code is None:
        supported = "relevance, date, citation, comprehensive"
        raise SearchError(f"unsupported sort_by {sort_by!r}; supported: {supported}")
    return code


def _apply_sort(page: Any, sort_by: str | None) -> None:
    """Apply one verified sort option to professional-search results."""
    sort_code = _normalize_sort_by(sort_by)
    if sort_code is None:
        return
    result = page.evaluate(
        """(sortCode) => {
            const item = document.querySelector(`li[data-sort="${sortCode}"]`);
            if (!item) return {applied: false};
            if (!item.classList.contains("cur")) item.click();
            return {applied: true};
        }""",
        sort_code,
    )
    if not isinstance(result, dict) or not result.get("applied"):
        raise SearchError(f"CNKI sort option is unavailable: {sort_by}")
    page.wait_for_timeout(3000)
    _wait_for_selector(page, "#gridTable, .result-table-list, #briefRequest")


def _turn_to_page(page: Any, page_number: int) -> bool:
    """Move a professional-search result page to a later page."""
    if page_number <= 1:
        return True
    try:
        previous_signature = page.evaluate(
            """() => {
                const firstRow = document.querySelector(
                    "#gridTable tbody tr, .result-table-list tbody tr"
                );
                return firstRow ? firstRow.innerText.trim() : "";
            }"""
        )
        clicked = page.evaluate(
            """(targetPage) => {
                const link = document.querySelector(
                    `.pages a[data-curpage="${targetPage}"], ` +
                    `#PageNext[data-curpage="${targetPage}"], ` +
                    `#Page_next[data-curpage="${targetPage}"]`
                );
                if (!link) {
                    return false;
                }
                link.click();
                return true;
            }""",
            str(page_number),
        )
        if not clicked:
            return False
        page.wait_for_function(
            """(payload) => {
                const current = document.querySelector("#curPageHid");
                const firstRow = document.querySelector(
                    "#gridTable tbody tr, .result-table-list tbody tr"
                );
                const signature = firstRow ? firstRow.innerText.trim() : "";
                return current && current.value === payload.targetPage &&
                    signature && signature !== payload.previousSignature;
            }""",
            arg={
                "targetPage": str(page_number),
                "previousSignature": previous_signature,
            },
            timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
        )
        _wait_for_selector(page, "#gridTable, .result-table-list, #briefRequest")
        return True
    except SearchError:
        raise
    except Exception as exc:
        _raise_for_security_verification(page)
        raise SearchError(
            f"failed to load professional-search page {page_number}"
        ) from exc


def _search_page(
    page: Any,
    expression: str,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
    filter_payload: dict[str, Any] | None = None,
    sort_by: str | None = None,
    limit: int = 10,
    max_pages: int = 1,
) -> list[SearchResult]:
    """Submit one expression in an existing browser session."""
    page.goto(
        CNKI_PROFESSIONAL_SEARCH_URL,
        wait_until="domcontentloaded",
        timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
    )
    year_applied = _submit(page, expression, year_from, year_to)
    if _is_empty_result_page(page):
        return []
    _apply_result_filters(page, filter_payload)
    _apply_sort(page, sort_by)
    has_year_filter = year_from is not None or year_to is not None
    collect_all_pages = has_year_filter and not year_applied
    results: list[SearchResult] = []
    for page_number in range(1, max_pages + 1):
        if page_number > 1 and not _turn_to_page(page, page_number):
            break
        results.extend(parse(page))
        if not collect_all_pages and len(results) >= limit:
            break
    return results if collect_all_pages else results[:limit]


def _validate_run_options(limit: int, max_pages: int) -> None:
    """Validate shared professional-search execution options."""
    if limit < 1:
        raise SearchError("limit must be greater than zero")
    if max_pages < 1:
        raise SearchError("max_pages must be greater than zero")


def _filter_by_year_range(
    results: list[SearchResult],
    year_from: int | None,
    year_to: int | None,
) -> list[SearchResult]:
    """Validate a requested year range locally after page-level filtering."""
    if year_from is None and year_to is None:
        return results
    start = year_from if year_from is not None else year_to
    end = year_to if year_to is not None else year_from
    if start is None or end is None:
        return results
    if end < start:
        raise SearchError("year_to must be greater than or equal to year_from")
    return [
        result
        for result in results
        if result.year is not None and start <= result.year <= end
    ]


def _filter_by_year(
    results: list[SearchResult],
    year: int | None,
) -> list[SearchResult]:
    """Validate one requested year locally."""
    return _filter_by_year_range(results, year, year)


@rate_limited(profile=None)
def run_expression_on_page(
    page: Any,
    expression: str,
    *,
    year: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    filter_payload: dict[str, Any] | None = None,
    sort_by: str | None = None,
    limit: int = 10,
    max_pages: int = 1,
) -> list[SearchResult]:
    """Run a trusted professional expression on an existing browser page."""
    try:
        expression = expression.strip()
        if not expression:
            raise SearchError("professional search expression is required")
        _validate_run_options(limit, max_pages)
        start_year = year_from if year_from is not None else year
        end_year = year_to if year_to is not None else year
        results = _search_page(
            page,
            expression,
            year_from=start_year,
            year_to=end_year,
            filter_payload=filter_payload,
            sort_by=sort_by,
            limit=limit,
            max_pages=max_pages,
        )
        return _filter_by_year_range(results, start_year, end_year)
    except ParseError as exc:
        raise SearchError(
            f"failed to parse professional-search results: {exc}"
        ) from exc
    except SearchError:
        raise
    except Exception as exc:
        _raise_for_security_verification(page)
        raise SearchError(f"professional search failed: {exc}") from exc


def _run_expression(
    expression: str,
    *,
    year: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    filter_payload: dict[str, Any] | None = None,
    sort_by: str | None = None,
    profile: str | None = None,
    limit: int = 10,
    max_pages: int = 1,
) -> list[SearchResult]:
    """Run one trusted CNKI professional-search expression."""
    try:
        ensure_login(profile=profile)
        with Runtime(profile=profile) as runtime:
            return run_expression_on_page(
                runtime.get_page(),
                expression,
                year=year,
                year_from=year_from,
                year_to=year_to,
                filter_payload=filter_payload,
                sort_by=sort_by,
                limit=limit,
                max_pages=max_pages,
            )
    except SearchError:
        raise
    except Exception as exc:
        _raise_for_security_verification(locals().get("page"))
        raise SearchError(f"professional search failed: {exc}") from exc


def _run(
    query: CnkiQuery,
    *,
    profile: str | None = None,
    limit: int = 10,
    max_pages: int = 1,
    year_from: int | None = None,
    year_to: int | None = None,
    filter_payload: dict[str, Any] | None = None,
    sort_by: str | None = None,
) -> list[SearchResult]:
    """Run a structured CNKI query with wide-to-strict fallbacks."""
    try:
        _validate_run_options(limit, max_pages)
        expressions = build_expressions(query)
        probe_limit = max(limit, 2)
        ensure_login(profile=profile)
        with Runtime(profile=profile) as runtime:
            page = runtime.get_page()
            best_results: list[SearchResult] = []
            start_year = year_from if year_from is not None else query.year
            end_year = year_to if year_to is not None else query.year
            for index, expression in enumerate(expressions):
                results = _filter_by_year_range(
                    _search_page(
                        page,
                        expression,
                        year_from=start_year,
                        year_to=end_year,
                        filter_payload=filter_payload,
                        sort_by=sort_by,
                        limit=probe_limit,
                        max_pages=max_pages,
                    ),
                    start_year,
                    end_year,
                )
                if index == 0 and len(results) <= 1:
                    return results[:limit]
                if len(results) == 1:
                    return results[:limit]
                if results:
                    best_results = results
            return best_results[:limit]
    except ParseError as exc:
        raise SearchError(
            f"failed to parse professional-search results: {exc}"
        ) from exc
    except SearchError:
        raise
    except Exception as exc:
        _raise_for_security_verification(locals().get("page"))
        raise SearchError(f"professional search failed: {exc}") from exc


@rate_limited(profile=None)
def run(
    query: CnkiQuery,
    *,
    profile: str | None = None,
    limit: int = 10,
    max_pages: int = 1,
    year_from: int | None = None,
    year_to: int | None = None,
    filter_payload: dict[str, Any] | None = None,
    sort_by: str | None = None,
) -> list[SearchResult]:
    """Run a rate-limited CNKI professional search."""
    return _run(
        query,
        profile=profile,
        limit=limit,
        max_pages=max_pages,
        year_from=year_from,
        year_to=year_to,
        filter_payload=filter_payload,
        sort_by=sort_by,
    )


__all__ = [
    "PROFESSIONAL_SEARCH_GUIDE",
    "build_filtered_expression",
    "build_expression",
    "build_expressions",
    "build_structured_expression",
    "run",
    "run_expression_on_page",
]
