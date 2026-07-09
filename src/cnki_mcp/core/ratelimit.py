#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/ratelimit.py

"""Request rate limiting and daily quota tracking."""

import functools
import json
import time
from collections.abc import Callable
from datetime import date
from typing import Any, TypeVar

from .config import (
    DAILY_REQUEST_QUOTA,
    RATE_LIMIT_REQUESTS_PER_SECOND,
    get_profile_path,
)
from .exceptions import RateLimited

F = TypeVar("F", bound=Callable[..., Any])


class RateLimiter:
    """Enforces a minimum interval between consecutive requests."""

    def __init__(
        self,
        requests_per_second: float = RATE_LIMIT_REQUESTS_PER_SECOND,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            requests_per_second: Maximum allowed requests per second.
        """
        self._min_interval = 1.0 / requests_per_second
        self._last_request_time: float | None = None

    def acquire(self) -> None:
        """Block until the next request is allowed."""
        now = time.time()
        if self._last_request_time is not None:
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()


class QuotaTracker:
    """Tracks daily request quotas per profile."""

    def __init__(
        self,
        profile: str | None = None,
        daily_quota: int = DAILY_REQUEST_QUOTA,
    ) -> None:
        """Initialize the quota tracker for a profile.

        Args:
            profile: Optional profile name; defaults to the current default.
            daily_quota: Maximum requests allowed per day.
        """
        self._profile_path = get_profile_path(profile)
        self._daily_quota = daily_quota
        self._quota_path = self._profile_path / "quota.json"

    def _load_quota(self) -> dict[str, Any]:
        """Load quota state from disk or return defaults."""
        if not self._quota_path.exists():
            return {"date": "", "count": 0}
        try:
            with self._quota_path.open(encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"date": "", "count": 0}

    def _save_quota(self, count: int, date_str: str) -> None:
        """Persist quota state to disk."""
        self._profile_path.mkdir(parents=True, exist_ok=True)
        with self._quota_path.open("w", encoding="utf-8") as f:
            json.dump({"date": date_str, "count": count}, f, indent=2)

    def check_quota(self) -> None:
        """Raise RateLimited if the daily quota has been reached.

        Raises:
            RateLimited: When the profile's daily quota is exhausted.
        """
        today = date.today().isoformat()
        state = self._load_quota()
        count = 0 if state.get("date") != today else int(state.get("count", 0))
        if count >= self._daily_quota:
            raise RateLimited(
                f"daily quota exceeded for profile {self._profile_path.name}: "
                f"{count}/{self._daily_quota}"
            )

    def record_request(self) -> None:
        """Increment the request count for the current day."""
        today = date.today().isoformat()
        state = self._load_quota()
        if state.get("date") != today:
            count = 1
        else:
            count = int(state.get("count", 0)) + 1
        self._save_quota(count, today)


def rate_limited(profile: str | None = None) -> Callable[[F], F]:
    """Decorator that applies rate limiting and quota tracking.

    Args:
        profile: Optional profile name; defaults to the current default.

    Returns:
        A decorator that wraps the target function.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            QuotaTracker(profile).check_quota()
            RateLimiter().acquire()
            result = func(*args, **kwargs)
            QuotaTracker(profile).record_request()
            return result

        return wrapper

    return decorator


__all__ = [
    "RateLimiter",
    "QuotaTracker",
    "rate_limited",
]
