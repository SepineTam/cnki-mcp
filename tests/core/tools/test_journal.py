#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/tools/test_journal.py

"""Tests for core/tools/journal.py."""

from unittest.mock import MagicMock, patch

import pytest

from cnki_mcp.core.exceptions import (
    IssueNotAvailable,
    JournalLookupError,
    JournalNotFound,
)
from cnki_mcp.core.models import Article, JournalRecord, SearchResult
from cnki_mcp.core.tools import journal


def _record() -> JournalRecord:
    """Build one resolved navigation identity."""
    return JournalRecord(
        name="经济学(季刊)",
        url="https://navi.cnki.net/knavi/detail?p=fresh",
        issn="2095-1086",
        code="JJXU",
    )


def _candidate(identifier: str, *, authors: list[str] | None = None) -> SearchResult:
    """Build one navi issue candidate."""
    return SearchResult(
        article_id=identifier,
        title=identifier,
        authors=authors if authors is not None else ["Author"],
        year=2026,
        source="经济学(季刊)",
        url=f"https://kns.cnki.net/{identifier}",
    )


def _article(identifier: str) -> Article:
    """Build complete metadata for one issue article."""
    return Article(
        article_id=identifier,
        title=identifier,
        authors=["Author"],
        year=2026,
        source="经济学(季刊)",
        volume="26",
        issue="01",
        pages="1-20",
        url=f"https://kns.cnki.net/{identifier}",
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"year": 2026, "vol": 1}, "issn"),
        ({"issn": "bad", "year": 2026, "vol": 1}, "ISSN"),
        ({"issn": "1002-9621", "year": 2026, "vol": ""}, "vol"),
    ],
)
def test_validate_request_rejects_ambiguous_or_invalid_input(
    kwargs: dict[str, object],
    message: str,
) -> None:
    """A valid ISSN and a non-empty issue number are mandatory."""
    with pytest.raises(JournalLookupError, match=message):
        journal.validate_request(**kwargs)


def test_build_search_url_ignores_spaces_and_punctuation() -> None:
    """Common spellings share one stable punctuation-free navi query."""
    urls = {
        journal.build_search_url(value)
        for value in ("经济学季刊", "经济学（季刊）", "经济学(季刊)")
    }

    assert len(urls) == 1
    url = urls.pop()
    assert url.startswith("https://navi.cnki.net/knavi/journals/search?")
    assert "field=TI" in url
    assert "%E7%BB%8F%E6%B5%8E%E5%AD%A6%E5%AD%A3%E5%88%8A" in url
    assert "p=" not in url


@patch("cnki_mcp.core.tools.journal.journal_parser.parse_journal_record")
@patch("cnki_mcp.core.tools.journal.journal_parser.parse_search_results")
def test_resolve_journal_uses_exact_normalized_name(
    mock_parse_search: MagicMock,
    mock_parse_record: MagicMock,
) -> None:
    """A fuzzy navi result page is narrowed to the exact journal name."""
    page = MagicMock()
    wrong = JournalRecord(name="经济学动态", url="https://navi/wrong")
    exact = JournalRecord(name="经济学(季刊)", url="https://navi/right")
    mock_parse_search.return_value = [wrong, exact]
    mock_parse_record.return_value = _record()

    result = journal.resolve_journal_on_page(page, "经济学（季刊）")

    page.goto.assert_any_call(
        journal.build_search_url("经济学（季刊）"),
        wait_until="domcontentloaded",
        timeout=journal.PAGE_LOAD_TIMEOUT_SECONDS * 1000,
    )
    page.goto.assert_called_with(
        exact.url,
        wait_until="domcontentloaded",
        timeout=journal.PAGE_LOAD_TIMEOUT_SECONDS * 1000,
    )
    assert result == _record()


@patch("cnki_mcp.core.tools.journal.journal_parser.parse_search_results")
def test_resolve_journal_raises_for_missing_exact_name(
    mock_parse_search: MagicMock,
) -> None:
    """Fuzzy neighbors do not silently replace a missing exact journal."""
    mock_parse_search.return_value = [
        JournalRecord(name="世界经济研究", url="https://navi/other")
    ]

    with pytest.raises(JournalNotFound, match="世界经济"):
        journal.resolve_journal_on_page(MagicMock(), "世界经济")


@patch("cnki_mcp.core.tools.journal._load_journal_record")
@patch("cnki_mcp.core.tools.journal._search_journal_cards")
def test_search_issn_returns_every_resolved_candidate(
    mock_search: MagicMock,
    mock_load: MagicMock,
) -> None:
    """The lookup maps every navi search result to its displayed ISSN."""
    first = JournalRecord(name="经济学(季刊)", url="https://navi/one")
    second = JournalRecord(name="经济学动态", url="https://navi/two")
    mock_search.return_value = [first, second]
    mock_load.side_effect = [
        JournalRecord(
            name="经济学(季刊)",
            url=first.url,
            issn="2095-1086",
            code="JJXU",
        ),
        JournalRecord(
            name="经济学动态",
            url=second.url,
            issn="1002-8390",
            code="JJXD",
        ),
    ]

    result = journal.search_issn_on_page(object(), "经济学季刊")

    assert result == {
        "经济学(季刊)": "2095-1086",
        "经济学动态": "1002-8390",
    }


@patch("cnki_mcp.core.tools.journal.journal_parser.parse_issue_html")
@patch("cnki_mcp.core.tools.journal._fetch_issue_html")
def test_collect_issue_catalog_fetches_every_page(
    mock_fetch: MagicMock,
    mock_parse: MagicMock,
) -> None:
    """Catalog pagination continues until the navi raw total is collected."""
    first_page = [_candidate(f"id-{index}") for index in range(20)]
    second_page = [_candidate(f"id-{index}") for index in range(20, 23)]
    mock_fetch.side_effect = ["page-0", "page-1"]
    mock_parse.side_effect = [(first_page, 23), (second_page, 23)]

    results = journal._collect_issue_catalog(
        object(),
        _record(),
        token="dynamic-token",
        year=2026,
    )

    assert len(results) == 23
    assert mock_fetch.call_count == 2


@patch("cnki_mcp.core.tools.journal.metadata.run_on_page")
@patch("cnki_mcp.core.tools.journal._collect_issue_catalog")
@patch("cnki_mcp.core.tools.journal._find_issue_token")
@patch("cnki_mcp.core.tools.journal._resolve_request_journal")
def test_run_on_page_uses_navi_catalog_and_expands_complete_metadata(
    mock_resolve: MagicMock,
    mock_token: MagicMock,
    mock_catalog: MagicMock,
    mock_metadata: MagicMock,
) -> None:
    """Issue rows come from navi and only article rows load detail metadata."""
    mock_resolve.return_value = _record()
    mock_token.return_value = "dynamic-token"
    article_candidates = [_candidate("one"), _candidate("two")]
    notice = _candidate("notice", authors=[])
    mock_catalog.return_value = [*article_candidates, notice]
    mock_metadata.side_effect = [_article("one"), _article("two")]

    result = journal.run_on_page(
        object(),
        issn="2095-1086",
        year=2026,
        vol=1,
    )

    assert result.name == "经济学(季刊)"
    assert result.issn == "2095-1086"
    assert result.volume == "26"
    assert result.issue == "01"
    assert [article.title for article in result.articles] == ["one", "two"]
    assert mock_metadata.call_count == 2


@patch("cnki_mcp.core.tools.journal._find_issue_token", return_value=None)
@patch("cnki_mcp.core.tools.journal._resolve_request_journal")
def test_run_on_page_raises_when_issue_is_not_published(
    mock_resolve: MagicMock,
    mock_token: MagicMock,
) -> None:
    """A missing navi year/issue node has the specific unavailable error."""
    mock_resolve.return_value = _record()

    with pytest.raises(IssueNotAvailable, match="2099"):
        journal.run_on_page(
            object(),
            issn="2095-1086",
            year=2099,
            vol=1,
        )

    mock_token.assert_called_once()


@patch("cnki_mcp.core.tools.journal.metadata.run_on_page")
@patch("cnki_mcp.core.tools.journal._collect_issue_catalog")
@patch("cnki_mcp.core.tools.journal._find_issue_token")
@patch("cnki_mcp.core.tools.journal._resolve_request_journal")
def test_run_on_page_retries_transient_detail_failure(
    mock_resolve: MagicMock,
    mock_token: MagicMock,
    mock_catalog: MagicMock,
    mock_metadata: MagicMock,
) -> None:
    """A transient detail failure is retried before the issue is rejected."""
    mock_resolve.return_value = _record()
    mock_token.return_value = "dynamic-token"
    mock_catalog.return_value = [_candidate("one")]
    mock_metadata.side_effect = [RuntimeError("temporary"), _article("one")]

    result = journal.run_on_page(
        object(),
        issn="2095-1086",
        year=2026,
        vol=1,
    )

    assert result.count == 1
    assert mock_metadata.call_count == 2
