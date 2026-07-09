#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/runtime.py

"""Playwright persistent context lifecycle management."""

from typing import TYPE_CHECKING

from playwright.sync_api import BrowserContext, Page, sync_playwright

from .config import get_profile_path
from .exceptions import CnkiMcpError

if TYPE_CHECKING:
    from playwright.sync_api import Playwright


class Runtime:
    """Manages a single Playwright persistent context bound to a profile."""

    def __init__(self, profile: str | None = None, headless: bool = False) -> None:
        """Initialize a runtime bound to a profile.

        Args:
            profile: Optional profile name; defaults to the current default.
            headless: Whether to run the browser without a visible window.
        """
        self._profile = profile
        self._headless = headless
        self._profile_path = get_profile_path(profile)
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def current_profile(self) -> str:
        """Return the resolved profile name."""
        return self._profile_path.name

    def start(self) -> Page:
        """Start the persistent browser context and return a new page.

        Returns:
            A new Playwright page.

        Raises:
            CnkiMcpError: If the browser context cannot be started.
        """
        try:
            self._playwright = sync_playwright().start()
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_path),
                headless=self._headless,
                viewport={"width": 1280, "height": 720},
            )
            self._page = self._context.new_page()
            return self._page
        except Exception as exc:
            self.close()
            raise CnkiMcpError(f"failed to start browser context: {exc}") from exc

    def get_page(self) -> Page:
        """Return the current page, creating one if necessary.

        Returns:
            The active Playwright page.
        """
        if self._page is not None and not self._page.is_closed():
            return self._page
        return self.start()

    def close(self) -> None:
        """Close the page, context, and playwright instance if open."""
        if self._page is not None and not self._page.is_closed():
            self._page.close()
        if self._context is not None:
            self._context.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._page = None
        self._context = None
        self._playwright = None

    def __enter__(self) -> "Runtime":
        """Enter the runtime context manager."""
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit the runtime context manager and close resources."""
        self.close()


def get_page(profile: str | None = None) -> Page:
    """Create a temporary Runtime and return its page.

    Note:
        The caller is responsible for closing the returned page/context.

    Args:
        profile: Optional profile name; defaults to the current default.

    Returns:
        A new Playwright page.
    """
    runtime = Runtime(profile=profile)
    return runtime.start()


__all__ = [
    "Runtime",
    "get_page",
]
