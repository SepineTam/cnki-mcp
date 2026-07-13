#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/test_config.py

"""Tests for core/config.py."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from cnki_mcp.core import config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path) -> Iterator[None]:
    """Redirect config paths into a temporary directory."""
    profiles = tmp_path / "profiles"
    downloads = tmp_path / "downloads"
    with patch.object(config, "BASE_DIR", tmp_path):
        with patch.object(config, "PROFILES_DIR", profiles):
            with patch.object(config, "PROFILE_CONFIG_PATH", profiles / "config.json"):
                with patch.object(config, "DOWNLOADS_DIR", downloads):
                    yield


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("profile1", True),
        ("my-profile", True),
        ("my_profile", True),
        ("a", True),
        ("", False),
        ("a/b", False),
        ("..", False),
        ("a b", False),
        ("a.b", False),
    ],
)
def test_validate_profile_name(name: str, valid: bool) -> None:
    """Profile name validation accepts safe identifiers only."""
    if valid:
        assert config.validate_profile_name(name) == name
    else:
        with pytest.raises(ValueError):
            config.validate_profile_name(name)


def test_get_profile_path_default() -> None:
    """Default profile path resolves to the fallback profile."""
    path = config.get_profile_path()
    assert path.name == "profile1"
    assert path.parent.name == "profiles"


def test_get_profile_path_explicit() -> None:
    """Explicit profile name is validated and returned as a path."""
    path = config.get_profile_path("profile2")
    assert path.name == "profile2"


def test_ensure_profile_dir_creates_directory() -> None:
    """ensure_profile_dir creates the profile directory."""
    path = config.ensure_profile_dir("profile1")
    assert path.exists()
    assert path.is_dir()


def test_get_default_profile_empty_environment() -> None:
    """No config and no directories falls back to profile1."""
    assert config.get_default_profile() == "profile1"


def test_get_default_profile_from_config() -> None:
    """config.json default_profile is respected."""
    config.PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    config.set_default_profile("profile2")
    assert config.get_default_profile() == "profile2"


def test_get_default_profile_from_existing_directories() -> None:
    """Without config.json, the first alphabetical directory is chosen."""
    (config.PROFILES_DIR / "alpha").mkdir(parents=True)
    (config.PROFILES_DIR / "beta").mkdir(parents=True)
    assert config.get_default_profile() == "alpha"


def test_set_default_profile_writes_config() -> None:
    """set_default_profile persists the choice."""
    config.set_default_profile("gamma")
    assert config.PROFILE_CONFIG_PATH.exists()
    assert config.get_default_profile() == "gamma"


def test_list_profiles_filters_files() -> None:
    """list_profiles returns only directory names, sorted."""
    (config.PROFILES_DIR / "zzz").mkdir(parents=True)
    (config.PROFILES_DIR / "aaa").mkdir(parents=True)
    (config.PROFILES_DIR / "not-a-dir.txt").write_text("x")
    assert config.list_profiles() == ["aaa", "zzz"]


def test_get_downloads_dir_creates_directory() -> None:
    """get_downloads_dir creates and returns the downloads path."""
    path = config.get_downloads_dir()
    assert path.exists()
    assert path.name == "downloads"
