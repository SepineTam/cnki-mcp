#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/test_exceptions.py

"""Tests for core/exceptions.py."""

from cnki_mcp.core.exceptions import (
    AuthError,
    AuthTimeout,
    CnkiMcpError,
    LoginFailed,
    LoginRequired,
    MetadataError,
    ParseError,
    RateLimited,
    SearchError,
)


def test_exception_hierarchy() -> None:
    """All custom exceptions inherit from CnkiMcpError."""
    exceptions = [
        AuthError("x"),
        LoginRequired("x"),
        LoginFailed("x"),
        AuthTimeout("x"),
        RateLimited("x"),
        ParseError("x"),
        SearchError("x"),
        MetadataError("x"),
    ]
    for exc in exceptions:
        assert isinstance(exc, CnkiMcpError)
        assert isinstance(exc, Exception)


def test_auth_errors_inherit_auth_error() -> None:
    """Authentication-specific errors inherit from AuthError."""
    assert issubclass(LoginRequired, AuthError)
    assert issubclass(LoginFailed, AuthError)
    assert issubclass(AuthTimeout, AuthError)
