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
from .models import Article, AuthState, LoginResult, SearchResult
from .tools import metadata, search


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
        **kwargs: Any,
    ) -> list[SearchResult]:
        """Search CNKI and return parsed results.

        Args:
            query: Search query string.
            limit: Maximum number of results to return.
            **kwargs: Additional search options forwarded to the search tool.

        Returns:
            List of search results.
        """
        self._ensure_login()
        return search.run(query, profile=self._profile, limit=limit, **kwargs)

    def get_metadata(self, article_id: str) -> Article:
        """Fetch metadata for a CNKI article.

        Args:
            article_id: Article identifier.

        Returns:
            Parsed article metadata.
        """
        self._ensure_login()
        return metadata.run(article_id, profile=self._profile)

    def __enter__(self) -> "CnkiClient":
        """Enter the client context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the client context manager."""
        pass


__all__ = ["CnkiClient"]
