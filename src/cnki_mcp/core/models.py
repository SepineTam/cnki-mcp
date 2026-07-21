#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/models.py

"""Data models used across the cnki-mcp package."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AuthState:
    """Represents the authentication state for a single profile."""

    is_logged_in: bool
    institution: str | None = None
    profile: str = "profile1"
    logged_in_at: datetime | None = None


@dataclass
class LoginResult:
    """Represents the outcome of a login attempt."""

    success: bool
    message: str
    auth_state: AuthState


@dataclass
class SearchResult:
    """Represents a single CNKI search result item."""

    article_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    date: str | None = None
    source: str | None = None
    url: str | None = None
    citation_count: int | None = None
    filename: str | None = None
    dbcode: str | None = None
    dbname: str | None = None
    export_id: str | None = None

    @property
    def journal(self) -> str | None:
        """Return the publication source using the public field name."""
        return self.source

    def to_public_dict(self) -> dict[str, object]:
        """Return the intentionally small public search-result shape."""
        return {
            "title": self.title,
            "authors": list(self.authors),
            "journal": self.journal,
            "date": self.date,
        }


@dataclass
class SearchFilters:
    """Represents optional filters applied to a CNKI search."""

    year_from: int | None = None
    year_to: int | None = None
    journal: str | None = None
    document_type: str | None = None
    source_types: list[str] = field(default_factory=list)
    author: str | None = None
    institution: str | None = None

    def is_empty(self) -> bool:
        """Return whether no filter is configured."""
        return not any(
            [
                self.year_from,
                self.year_to,
                self.journal,
                self.document_type,
                self.source_types,
                self.author,
                self.institution,
            ]
        )


@dataclass
class Article:
    """Represents detailed metadata for a CNKI article."""

    article_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    institution: str | None = None
    abstract: str | None = None
    keywords: list[str] | None = None
    year: int | None = None
    source: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None
    download_url: str | None = None


@dataclass
class JournalRecord:
    """Represents one journal resolved through CNKI navigation."""

    name: str
    url: str
    issn: str | None = None
    code: str | None = None


@dataclass
class JournalIssue:
    """Represents all parsed articles in one published journal issue."""

    name: str
    year: int
    issue: str
    volume: str | None = None
    issn: str | None = None
    articles: list[Article] = field(default_factory=list)

    @property
    def count(self) -> int:
        """Return the number of articles in the issue."""
        return len(self.articles)


__all__ = [
    "AuthState",
    "LoginResult",
    "SearchResult",
    "SearchFilters",
    "Article",
    "JournalRecord",
    "JournalIssue",
]
