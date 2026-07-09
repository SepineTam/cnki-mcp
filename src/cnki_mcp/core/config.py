#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/config.py

"""Configuration, paths, and profile helpers for cnki-mcp."""

import json
import re
from pathlib import Path

BASE_DIR = Path.home() / ".cnki-mcp"
PROFILES_DIR = BASE_DIR / "profiles"
PROFILE_CONFIG_PATH = PROFILES_DIR / "config.json"
DOWNLOADS_DIR = BASE_DIR / "downloads"

AUTH_TIMEOUT_SECONDS = 120
PAGE_LOAD_TIMEOUT_SECONDS = 30
CNKI_HOME_URL = "https://www.cnki.net/"
CNKI_LOGIN_URL = "https://fsso.cnki.net/"
RATE_LIMIT_REQUESTS_PER_SECOND = 1.0
DAILY_REQUEST_QUOTA = 1000

_PROFILE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_profile_name(name: str) -> str:
    """Validate and return a profile name.

    Args:
        name: Profile name to validate.

    Returns:
        The validated profile name.

    Raises:
        ValueError: If the profile name contains illegal characters.
    """
    if not name or not _PROFILE_NAME_PATTERN.match(name):
        raise ValueError(f"illegal profile name: {name!r}")
    return name


def get_default_profile() -> str:
    """Resolve the default profile name.

    Returns:
        The configured default profile, the first existing profile directory,
        or "profile1" as a fallback.
    """
    if PROFILE_CONFIG_PATH.exists():
        try:
            with PROFILE_CONFIG_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
            configured = data.get("default_profile")
            if isinstance(configured, str) and configured:
                return validate_profile_name(configured)
        except (OSError, json.JSONDecodeError):
            pass

    if PROFILES_DIR.exists():
        dirs = sorted(
            p.name for p in PROFILES_DIR.iterdir() if p.is_dir() and p.name
        )
        if dirs:
            return validate_profile_name(dirs[0])

    return "profile1"


def get_profile_path(profile: str | None = None) -> Path:
    """Return the profile directory path without creating it.

    Args:
        profile: Optional profile name; defaults to the current default profile.

    Returns:
        Path to the profile directory.
    """
    if profile is None:
        profile = get_default_profile()
    else:
        profile = validate_profile_name(profile)
    return PROFILES_DIR / profile


def ensure_profile_dir(profile: str | None = None) -> Path:
    """Create and return the profile directory if it does not exist.

    Args:
        profile: Optional profile name; defaults to the current default profile.

    Returns:
        Path to the created profile directory.
    """
    path = get_profile_path(profile)
    path.mkdir(parents=True, exist_ok=True)
    return path


def set_default_profile(profile: str) -> None:
    """Persist the default profile name.

    Args:
        profile: Profile name to set as default.

    Raises:
        IOError: If the config file cannot be written.
    """
    validate_profile_name(profile)
    ensure_profile_dir(profile)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    with PROFILE_CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump({"default_profile": profile}, f, indent=2)


def list_profiles() -> list[str]:
    """List existing profile directory names.

    Returns:
        Sorted list of profile names.
    """
    if not PROFILES_DIR.exists():
        return []
    return sorted(
        p.name for p in PROFILES_DIR.iterdir() if p.is_dir() and p.name
    )


def get_downloads_dir() -> Path:
    """Return and create the downloads directory if needed.

    Returns:
        Path to the downloads directory.
    """
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOADS_DIR


__all__ = [
    "BASE_DIR",
    "PROFILES_DIR",
    "PROFILE_CONFIG_PATH",
    "DOWNLOADS_DIR",
    "AUTH_TIMEOUT_SECONDS",
    "PAGE_LOAD_TIMEOUT_SECONDS",
    "CNKI_HOME_URL",
    "CNKI_LOGIN_URL",
    "RATE_LIMIT_REQUESTS_PER_SECOND",
    "DAILY_REQUEST_QUOTA",
    "validate_profile_name",
    "get_profile_path",
    "ensure_profile_dir",
    "get_default_profile",
    "set_default_profile",
    "list_profiles",
    "get_downloads_dir",
]
