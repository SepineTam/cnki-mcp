#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/test_runtime.py

"""Tests for core/runtime.py."""

from pathlib import Path
from unittest.mock import patch

from cnki_mcp.core import config
from cnki_mcp.core.runtime import Runtime, get_page


class _MockContext:
    """Minimal BrowserContext stub."""

    def __init__(self) -> None:
        self.closed = False

    def new_page(self) -> "_MockPage":
        return _MockPage()

    def close(self) -> None:
        self.closed = True


class _MockPage:
    """Minimal Page stub."""

    def __init__(self) -> None:
        self._closed = False
        self.url = "about:blank"

    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True


class _MockPlaywright:
    """Minimal Playwright stub."""

    def __init__(self) -> None:
        self.stopped = False
        self.context = _MockContext()
        self.chromium = _MockChromium(self)

    def stop(self) -> None:
        self.stopped = True


class _MockChromium:
    """Chromium stub that returns a persistent context."""

    def __init__(self, playwright: _MockPlaywright) -> None:
        self._playwright = playwright

    def launch_persistent_context(self, **kwargs) -> _MockContext:
        return self._playwright.context


def _make_stub_playwright() -> _MockPlaywright:
    return _MockPlaywright()


def test_runtime_profile_resolution(tmp_path: Path) -> None:
    """Runtime resolves the profile from config."""
    with patch.object(config, "BASE_DIR", tmp_path):
        with patch.object(config, "PROFILES_DIR", tmp_path / "profiles"):
            rt = Runtime(profile="profile1")
            assert rt.current_profile == "profile1"


def test_runtime_get_page_reuses_page(tmp_path: Path) -> None:
    """get_page returns the same page until it is closed."""
    with patch.object(config, "BASE_DIR", tmp_path):
        with patch.object(config, "PROFILES_DIR", tmp_path / "profiles"):
            rt = Runtime(profile="profile1")
            with patch(
                "cnki_mcp.core.runtime.sync_playwright"
            ) as mock_sync_playwright:
                mock_sync_playwright.return_value.start.return_value = (
                    _make_stub_playwright()
                )
                page1 = rt.get_page()
                page2 = rt.get_page()
                assert page1 is page2


def test_runtime_close_cleans_up(tmp_path: Path) -> None:
    """close resets internal state."""
    with patch.object(config, "BASE_DIR", tmp_path):
        with patch.object(config, "PROFILES_DIR", tmp_path / "profiles"):
            rt = Runtime(profile="profile1")
            with patch(
                "cnki_mcp.core.runtime.sync_playwright"
            ) as mock_sync_playwright:
                mock_sync_playwright.return_value.start.return_value = (
                    _make_stub_playwright()
                )
                rt.start()
                rt.close()
                assert rt._context is None
                assert rt._page is None
                assert rt._playwright is None


def test_runtime_context_manager(tmp_path: Path) -> None:
    """Runtime works as a context manager."""
    with patch.object(config, "BASE_DIR", tmp_path):
        with patch.object(config, "PROFILES_DIR", tmp_path / "profiles"):
            with patch(
                "cnki_mcp.core.runtime.sync_playwright"
            ) as mock_sync_playwright:
                mock_sync_playwright.return_value.start.return_value = (
                    _make_stub_playwright()
                )
                with Runtime(profile="profile1") as rt:
                    page = rt.get_page()
                    assert page.url == "about:blank"


def test_get_page_helper(tmp_path: Path) -> None:
    """get_page creates a temporary Runtime page."""
    with patch.object(config, "BASE_DIR", tmp_path):
        with patch.object(config, "PROFILES_DIR", tmp_path / "profiles"):
            with patch(
                "cnki_mcp.core.runtime.sync_playwright"
            ) as mock_sync_playwright:
                mock_sync_playwright.return_value.start.return_value = (
                    _make_stub_playwright()
                )
                page = get_page(profile="profile1")
                assert page.url == "about:blank"
