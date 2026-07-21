#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/test_browser_worker.py

"""Tests for the single-thread persistent browser worker."""

import threading
from concurrent.futures import Future

import pytest

from cnki_mcp.core.browser_worker import BrowserWorker
from cnki_mcp.core.exceptions import LoginRequired


class FakeRuntime:
    """Record runtime lifecycle calls and their thread identifiers."""

    instances: list["FakeRuntime"] = []

    def __init__(self, profile: str | None = None) -> None:
        self.profile = profile
        self.page = object()
        self.start_thread: int | None = None
        self.close_thread: int | None = None
        self.closed = False
        self.__class__.instances.append(self)

    def start(self) -> object:
        self.start_thread = threading.get_ident()
        return self.page

    def get_page(self) -> object:
        return self.page

    def close(self) -> None:
        self.close_thread = threading.get_ident()
        self.closed = True


@pytest.fixture(autouse=True)
def reset_runtime_instances() -> None:
    """Reset recorded runtimes before every test."""
    FakeRuntime.instances = []


def test_worker_starts_calls_and_closes_on_one_thread() -> None:
    """Every Playwright-facing operation stays on the owner thread."""
    worker = BrowserWorker(runtime_factory=FakeRuntime)
    worker.start("school")

    call_thread = worker.call(lambda page: threading.get_ident())
    runtime = FakeRuntime.instances[0]
    worker.close()

    assert runtime.start_thread == call_thread
    assert runtime.close_thread == call_thread


def test_worker_serializes_concurrent_calls() -> None:
    """Concurrent callers execute browser tasks one at a time."""
    worker = BrowserWorker(runtime_factory=FakeRuntime)
    worker.start("school")
    order: list[str] = []
    first_entered = threading.Event()
    release_first = threading.Event()

    def first(page: object) -> str:
        order.append("first-start")
        first_entered.set()
        release_first.wait(timeout=2)
        order.append("first-end")
        return "first"

    def second(page: object) -> str:
        order.append("second")
        return "second"

    first_future: Future[str] = worker.submit(first)
    assert first_entered.wait(timeout=2)
    second_future: Future[str] = worker.submit(second)
    release_first.set()

    assert first_future.result(timeout=2) == "first"
    assert second_future.result(timeout=2) == "second"
    assert order == ["first-start", "first-end", "second"]
    worker.close()


def test_worker_start_is_idempotent_for_same_profile() -> None:
    """Repeated startup does not create another persistent browser."""
    worker = BrowserWorker(runtime_factory=FakeRuntime)

    worker.start("school")
    worker.start("school")

    assert len(FakeRuntime.instances) == 1
    worker.close()


def test_worker_switches_profile_after_closing_old_runtime() -> None:
    """Profile switching closes the old browser before opening the new one."""
    worker = BrowserWorker(runtime_factory=FakeRuntime)
    worker.start("first")
    first = FakeRuntime.instances[0]

    worker.start("second")

    assert first.closed is True
    assert worker.current_profile == "second"
    assert len(FakeRuntime.instances) == 2
    worker.close()


def test_worker_requires_login_before_browser_calls() -> None:
    """An inactive stdio worker gives a clear login instruction."""
    worker = BrowserWorker(runtime_factory=FakeRuntime)

    with pytest.raises(LoginRequired, match="login"):
        worker.call(lambda page: None)


def test_worker_can_restart_after_logout() -> None:
    """Closing and later logging in creates a fresh worker thread."""
    worker = BrowserWorker(runtime_factory=FakeRuntime)
    worker.start("first")
    worker.close()

    worker.start("second")

    assert worker.is_running is True
    assert worker.current_profile == "second"
    worker.close()


def test_refresh_browser_is_an_unimplemented_internal_stub() -> None:
    """The future recovery hook exists without changing browser state."""
    worker = BrowserWorker(runtime_factory=FakeRuntime)

    result = worker.refresh_browser()

    assert result == {"success": False, "error": "not implemented"}
