#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/test_ratelimit.py

"""Tests for core/ratelimit.py."""

import json
import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from cnki_mcp.core import config
from cnki_mcp.core.exceptions import RateLimited
from cnki_mcp.core.ratelimit import QuotaTracker, RateLimiter, rate_limited


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path) -> Iterator[None]:
    """Redirect config paths into a temporary directory."""
    profiles = tmp_path / "profiles"
    with patch.object(config, "BASE_DIR", tmp_path):
        with patch.object(config, "PROFILES_DIR", profiles):
            with patch.object(config, "PROFILE_CONFIG_PATH", profiles / "config.json"):
                yield


def test_rate_limiter_enforces_interval() -> None:
    """Two acquire calls respect the configured interval."""
    rl = RateLimiter(requests_per_second=2.0)
    start = time.time()
    rl.acquire()
    rl.acquire()
    elapsed = time.time() - start
    assert elapsed >= 0.5


def test_quota_tracker_records_request() -> None:
    """record_request increments the daily count."""
    qt = QuotaTracker(profile="profile1", daily_quota=10)
    qt.record_request()
    state = json.loads(qt._quota_path.read_text())
    assert state["count"] == 1


def test_quota_tracker_resets_on_date_change() -> None:
    """A stale date resets the count to one."""
    qt = QuotaTracker(profile="profile1", daily_quota=10)
    qt._save_quota(count=5, date_str="2000-01-01")
    qt.record_request()
    state = json.loads(qt._quota_path.read_text())
    assert state["count"] == 1


def test_quota_tracker_raises_when_exceeded() -> None:
    """check_quota raises RateLimited at the quota boundary."""
    qt = QuotaTracker(profile="profile1", daily_quota=2)
    qt.record_request()
    qt.record_request()
    with pytest.raises(RateLimited):
        qt.check_quota()


def test_quota_tracker_corrupted_file_fallback() -> None:
    """A corrupted quota file is treated as empty."""
    qt = QuotaTracker(profile="profile1", daily_quota=10)
    qt._profile_path.mkdir(parents=True, exist_ok=True)
    qt._quota_path.write_text("not json")
    qt.record_request()
    state = json.loads(qt._quota_path.read_text())
    assert state["count"] == 1


def test_rate_limited_decorator_records_quota() -> None:
    """The decorator checks quota and records a request."""
    call_count = 0

    @rate_limited(profile="profile1")
    def fetch() -> str:
        nonlocal call_count
        call_count += 1
        return "ok"

    result = fetch()
    assert result == "ok"
    assert call_count == 1
    qt = QuotaTracker(profile="profile1")
    state = json.loads(qt._quota_path.read_text())
    assert state["count"] == 1
