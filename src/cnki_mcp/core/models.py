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
    source: str | None = None
    url: str | None = None
    citation_count: int | None = None


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
    doi: str | None = None
    url: str | None = None
    download_url: str | None = None


__all__ = [
    "AuthState",
    "LoginResult",
    "SearchResult",
    "Article",
]
