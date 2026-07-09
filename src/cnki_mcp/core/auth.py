#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/auth.py

"""Authentication and profile state management for CNKI sessions."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError, sync_playwright

from . import config
from .exceptions import AuthTimeout, LoginFailed
from .models import AuthState, LoginResult

# Selectors that indicate a logged-in CNKI session on the homepage.
_LOGIN_SELECTORS = [
    "#UserName",
    "#Ecp_top_logout_layer",
    ".Ecp_members_logout",
    ".welcome-name",
    ".login-in .username",
    ".user-name",
    ".name-logged",
]


def get_profile_path(profile: str | None = None) -> Path:
    """Return the profile directory path without creating it.

    Args:
        profile: Optional profile name; defaults to the current default profile.

    Returns:
        Path to the profile directory.
    """
    return config.get_profile_path(profile)


def _save_context_state(context: Any, profile: str | None = None) -> None:
    """Persist browser context state to the profile directory."""
    resolved_profile = config.get_default_profile()
    if profile is not None:
        resolved_profile = config.validate_profile_name(profile)
    profile_path = config.ensure_profile_dir(resolved_profile)

    try:
        cookies_path = profile_path / "cookies.json"
        cookies = context.cookies()
        with cookies_path.open("w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        storage_path = profile_path / "storage_state.json"
        context.storage_state(path=str(storage_path))
    except Exception as exc:
        raise LoginFailed(
            f"failed to save context state to {profile_path}: {exc}"
        ) from exc


def _load_context_state(context: Any, profile: str | None = None) -> None:
    """Load previously persisted browser context state if available."""
    resolved_profile = config.get_default_profile()
    if profile is not None:
        resolved_profile = config.validate_profile_name(profile)
    profile_path = config.get_profile_path(resolved_profile)

    cookies_path = profile_path / "cookies.json"
    if cookies_path.exists():
        try:
            with cookies_path.open(encoding="utf-8") as f:
                cookies = json.load(f)
            if cookies:
                context.add_cookies(cookies)
        except (OSError, json.JSONDecodeError):
            pass

    storage_path = profile_path / "storage_state.json"
    if not storage_path.exists():
        return

    try:
        with storage_path.open(encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    origins = state.get("origins", [])
    if not origins:
        return

    page = context.new_page()
    try:
        for origin_state in origins:
            origin = origin_state.get("origin")
            if not origin:
                continue
            try:
                page.goto(
                    origin,
                    wait_until="domcontentloaded",
                    timeout=config.PAGE_LOAD_TIMEOUT_SECONDS * 1000,
                )
            except Exception:
                continue
            for item in origin_state.get("localStorage", []):
                key = item.get("name", "")
                value = item.get("value", "")
                if key:
                    page.evaluate(
                        """(kv) => { localStorage.setItem(kv[0], kv[1]); }""",
                        [key, value],
                    )
            for item in origin_state.get("sessionStorage", []):
                key = item.get("name", "")
                value = item.get("value", "")
                if key:
                    page.evaluate(
                        """(kv) => { sessionStorage.setItem(kv[0], kv[1]); }""",
                        [key, value],
                    )
    finally:
        page.close()


def is_logged_in(page: Any) -> bool:
    """Check whether the given page shows a logged-in CNKI session.

    Navigates to the CNKI homepage and looks for user-name elements that are
    only present when a session is authenticated. Any navigation or parsing
    failure is treated as not logged in.
    """
    try:
        page.goto(
            config.CNKI_HOME_URL,
            wait_until="networkidle",
            timeout=config.PAGE_LOAD_TIMEOUT_SECONDS * 1000,
        )
    except TimeoutError:
        return False
    except Exception:
        return False

    for selector in _LOGIN_SELECTORS:
        try:
            if page.locator(selector).count() > 0:
                return True
        except Exception:
            continue
    return False


def login(
    profile: str | None = None,
    headless: bool = False,
    timeout: int = config.AUTH_TIMEOUT_SECONDS,
) -> LoginResult:
    """Trigger an interactive CNKI login flow.

    Args:
        profile: Optional profile name; defaults to the current default profile.
        headless: Whether to run the browser in headless mode.
        timeout: Maximum seconds to wait for the user to complete login.

    Returns:
        A ``LoginResult`` describing the outcome.

    Raises:
        AuthTimeout: If the login flow exceeds the timeout.
        LoginFailed: If the login flow is cancelled or fails.
    """
    resolved_profile = config.get_default_profile()
    if profile is not None:
        resolved_profile = config.validate_profile_name(profile)
    profile_path = config.ensure_profile_dir(resolved_profile)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=headless,
        )
        _load_context_state(context, resolved_profile)

        page = context.new_page()
        try:
            if is_logged_in(page):
                return LoginResult(
                    success=True,
                    message="already logged in",
                    auth_state=AuthState(
                        is_logged_in=True,
                        institution=None,
                        profile=resolved_profile,
                        logged_in_at=datetime.now(UTC),
                    ),
                )

            page.goto(
                config.CNKI_LOGIN_URL,
                wait_until="networkidle",
                timeout=config.PAGE_LOAD_TIMEOUT_SECONDS * 1000,
            )
            print("请在弹出的浏览器窗口中完成学校/机构认证，完成后将自动保存登录状态。")

            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                if is_logged_in(page):
                    _save_context_state(context, resolved_profile)
                    return LoginResult(
                        success=True,
                        message="login successful",
                        auth_state=AuthState(
                            is_logged_in=True,
                            institution=None,
                            profile=resolved_profile,
                            logged_in_at=datetime.now(UTC),
                        ),
                    )
                if page.is_closed():
                    raise LoginFailed("browser closed before login completed")
                time.sleep(2)

            raise AuthTimeout(f"login not completed within {timeout} seconds")
        finally:
            page.close()
            context.close()


def logout(profile: str | None = None) -> None:
    """Clear persisted authentication state for a profile.

    Args:
        profile: Optional profile name; defaults to the current default profile.
    """
    profile_path = config.get_profile_path(profile)
    for filename in ("cookies.json", "storage_state.json"):
        file_path = profile_path / filename
        if file_path.exists():
            file_path.unlink()


def ensure_login(
    page: Any | None = None,
    profile: str | None = None,
    headless: bool = False,
    timeout: int = config.AUTH_TIMEOUT_SECONDS,
) -> AuthState:
    """Ensure the requested profile is logged in, triggering login if needed.

    Args:
        page: Optional existing page to check for login state.
        profile: Optional profile name; defaults to the current default profile.
        headless: Whether to run the browser in headless mode when logging in.
        timeout: Maximum seconds to wait for login.

    Returns:
        The current ``AuthState`` for the profile.
    """
    resolved_profile = config.get_default_profile()
    if profile is not None:
        resolved_profile = config.validate_profile_name(profile)

    if page is not None:
        if is_logged_in(page):
            return AuthState(
                is_logged_in=True,
                institution=None,
                profile=resolved_profile,
                logged_in_at=datetime.now(UTC),
            )
        result = login(profile=resolved_profile, headless=headless, timeout=timeout)
        return result.auth_state

    profile_path = config.ensure_profile_dir(resolved_profile)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=True,
        )
        _load_context_state(context, resolved_profile)
        check_page = context.new_page()
        try:
            already_logged_in = is_logged_in(check_page)
        finally:
            check_page.close()
            context.close()

    if already_logged_in:
        return AuthState(
            is_logged_in=True,
            institution=None,
            profile=resolved_profile,
            logged_in_at=datetime.now(UTC),
        )

    result = login(profile=resolved_profile, headless=headless, timeout=timeout)
    return result.auth_state


def refresh_login(
    profile: str | None = None,
    headless: bool = False,
    timeout: int = config.AUTH_TIMEOUT_SECONDS,
) -> LoginResult:
    """Clear the profile state and perform a fresh login.

    Args:
        profile: Optional profile name; defaults to the current default profile.
        headless: Whether to run the browser in headless mode.
        timeout: Maximum seconds to wait for login.

    Returns:
        A ``LoginResult`` describing the outcome.
    """
    logout(profile)
    return login(profile, headless=headless, timeout=timeout)


def list_profiles() -> list[str]:
    """Return a sorted list of existing profile names."""
    return config.list_profiles()


def get_default_profile() -> str:
    """Return the resolved default profile name."""
    return config.get_default_profile()


def set_default_profile(profile: str) -> None:
    """Persist the default profile name."""
    config.set_default_profile(profile)


__all__ = [
    "get_profile_path",
    "login",
    "logout",
    "ensure_login",
    "refresh_login",
    "list_profiles",
    "get_default_profile",
    "set_default_profile",
]
