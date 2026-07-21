#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/exceptions.py

"""Custom exceptions for the cnki-mcp package."""


class CnkiMcpError(Exception):
    """Base exception for all cnki-mcp errors."""


class AuthError(CnkiMcpError):
    """Base exception for authentication-related errors."""


class LoginRequired(AuthError):
    """Raised when a logged-in session is required but missing."""


class LoginFailed(AuthError):
    """Raised when the login flow fails or is cancelled by the user."""


class AuthTimeout(AuthError):
    """Raised when the login flow exceeds the configured timeout."""


class RateLimited(CnkiMcpError):
    """Raised when rate limits or daily quotas are exceeded."""


class ParseError(CnkiMcpError):
    """Raised when HTML or page parsing fails."""


class SearchError(CnkiMcpError):
    """Raised when the search workflow fails."""


class MetadataError(CnkiMcpError):
    """Raised when metadata retrieval fails."""


class JournalLookupError(CnkiMcpError):
    """Raised when a journal issue request cannot be completed."""


class JournalNotFound(JournalLookupError):
    """Raised when an exact journal cannot be resolved."""


class IssueNotAvailable(JournalLookupError):
    """Raised when a requested journal year or issue is unavailable."""


class DownloadError(CnkiMcpError):
    """Raised when full-text download fails."""


__all__ = [
    "CnkiMcpError",
    "AuthError",
    "LoginRequired",
    "LoginFailed",
    "AuthTimeout",
    "RateLimited",
    "ParseError",
    "SearchError",
    "MetadataError",
    "JournalLookupError",
    "JournalNotFound",
    "IssueNotAvailable",
    "DownloadError",
]
