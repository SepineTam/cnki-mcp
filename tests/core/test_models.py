#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/test_models.py

"""Tests for core/models.py."""

from datetime import datetime, timezone

from cnki_mcp.core.models import (
    Article,
    AuthState,
    JournalIssue,
    JournalRecord,
    LoginResult,
    SearchFilters,
    SearchResult,
)


def test_auth_state_defaults() -> None:
    """AuthState uses sensible defaults."""
    state = AuthState(is_logged_in=True)
    assert state.is_logged_in is True
    assert state.institution is None
    assert state.profile == "profile1"
    assert state.logged_in_at is None


def test_login_result_requires_fields() -> None:
    """LoginResult stores success, message, and auth state."""
    state = AuthState(
        is_logged_in=True,
        logged_in_at=datetime.now(timezone.utc),  # noqa: UP017
    )
    result = LoginResult(success=True, message="ok", auth_state=state)
    assert result.success is True
    assert result.message == "ok"
    assert result.auth_state is state


def test_search_result_defaults() -> None:
    """SearchResult provides empty author list by default."""
    result = SearchResult(article_id="id1", title="Title")
    assert result.authors == []
    assert result.year is None
    assert result.date is None
    assert result.source is None
    assert result.url is None
    assert result.citation_count is None


def test_search_result_public_shape_is_small_and_stable() -> None:
    """Public search output contains only basic citation fields."""
    result = SearchResult(
        article_id="internal-id",
        title="目标文章",
        authors=["作者甲", "作者乙"],
        date="2026-02-25",
        source="中国社会科学",
        filename="INTERNAL",
    )

    assert result.to_public_dict() == {
        "title": "目标文章",
        "authors": ["作者甲", "作者乙"],
        "journal": "中国社会科学",
        "date": "2026-02-25",
    }


def test_search_filters_defaults() -> None:
    """SearchFilters defaults to no active filters."""
    filters = SearchFilters()
    assert filters.is_empty() is True
    assert filters.source_types == []


def test_search_filters_detects_values() -> None:
    """SearchFilters detects configured filters."""
    filters = SearchFilters(year_from=2025, journal="图书馆论坛")
    assert filters.is_empty() is False


def test_article_defaults() -> None:
    """Article provides empty author list and None optional fields by default."""
    article = Article(article_id="id1", title="Title")
    assert article.authors == []
    assert article.institution is None
    assert article.abstract is None
    assert article.keywords is None
    assert article.year is None
    assert article.source is None
    assert article.doi is None
    assert article.url is None
    assert article.download_url is None


def test_journal_issue_reports_article_count() -> None:
    """JournalIssue groups complete metadata for one published issue."""
    issue = JournalIssue(
        name="世界经济",
        year=2026,
        issue="01",
        volume="49",
        issn="1002-9621",
        articles=[Article(article_id="id1", title="Title")],
    )

    assert issue.count == 1


def test_journal_record_keeps_fresh_navigation_identity() -> None:
    """JournalRecord carries resolved navi identity without persisting it."""
    record = JournalRecord(
        name="世界经济",
        url="https://navi.cnki.net/knavi/detail?p=fresh",
        issn="1002-9621",
        code="SJJJ",
    )

    assert record.name == "世界经济"
    assert record.issn == "1002-9621"
    assert record.code == "SJJJ"
