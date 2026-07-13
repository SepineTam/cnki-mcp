#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/test_auth.py

"""Tests for core/auth.py."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cnki_mcp.core import auth, config
from cnki_mcp.core.exceptions import AuthTimeout, LoginFailed


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path) -> Iterator[None]:
    """Redirect config paths into a temporary directory."""
    profiles = tmp_path / "profiles"
    with patch.object(config, "BASE_DIR", tmp_path):
        with patch.object(config, "PROFILES_DIR", profiles):
            with patch.object(config, "PROFILE_CONFIG_PATH", profiles / "config.json"):
                yield


def test_get_profile_path_default() -> None:
    """Default profile path falls back to profile1."""
    path = auth.get_profile_path()
    assert path.name == "profile1"


def test_get_profile_path_explicit() -> None:
    """Explicit profile path is validated."""
    path = auth.get_profile_path("profile2")
    assert path.name == "profile2"


def test_get_default_profile_empty() -> None:
    """No config or directories returns profile1."""
    assert auth.get_default_profile() == "profile1"


def test_get_default_profile_from_directories() -> None:
    """First alphabetical directory wins without config."""
    (config.PROFILES_DIR / "beta").mkdir(parents=True)
    (config.PROFILES_DIR / "alpha").mkdir(parents=True)
    assert auth.get_default_profile() == "alpha"


def test_set_default_profile_persists() -> None:
    """set_default_profile writes config.json."""
    auth.set_default_profile("profile2")
    assert auth.get_default_profile() == "profile2"


def test_logout_removes_state_files() -> None:
    """logout deletes cookies and storage state for the target profile."""
    profile_path = config.ensure_profile_dir("profile2")
    (profile_path / "cookies.json").write_text("[]")
    (profile_path / "storage_state.json").write_text("{}")
    auth.logout("profile2")
    assert not (profile_path / "cookies.json").exists()
    assert not (profile_path / "storage_state.json").exists()


def test_logout_does_not_touch_other_profiles() -> None:
    """logout only affects the requested profile."""
    p1 = config.ensure_profile_dir("profile1")
    p2 = config.ensure_profile_dir("profile2")
    (p1 / "cookies.json").write_text("[]")
    (p2 / "cookies.json").write_text("[]")
    auth.logout("profile2")
    assert (p1 / "cookies.json").exists()
    assert not (p2 / "cookies.json").exists()


def test_list_profiles_sorted() -> None:
    """list_profiles returns sorted directory names."""
    (config.PROFILES_DIR / "zzz").mkdir(parents=True)
    (config.PROFILES_DIR / "aaa").mkdir(parents=True)
    assert auth.list_profiles() == ["aaa", "zzz"]


def test_is_logged_in_true_when_user_element_present() -> None:
    """is_logged_in returns True when a user-name element exists."""
    page = MagicMock()
    page.locator.return_value.count.return_value = 1
    assert auth.is_logged_in(page) is True


def test_is_logged_in_false_when_no_user_element() -> None:
    """is_logged_in returns False when no user-name element exists."""
    page = MagicMock()
    page.locator.return_value.count.return_value = 0
    assert auth.is_logged_in(page) is False


def test_is_logged_in_false_on_timeout() -> None:
    """is_logged_in returns False on page timeout."""
    page = MagicMock()
    page.goto.side_effect = Exception("timeout")
    assert auth.is_logged_in(page) is False


def test_exception_types_exist() -> None:
    """Auth-specific exceptions are importable."""
    assert issubclass(AuthTimeout, Exception)
    assert issubclass(LoginFailed, Exception)
