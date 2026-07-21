#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/browser_worker.py

"""Single-thread owner for a persistent browser runtime."""

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock
from typing import Any, TypeVar

from .exceptions import LoginRequired
from .runtime import Runtime

ResultT = TypeVar("ResultT")


class BrowserWorker:
    """Keep a persistent Runtime and all browser calls on one thread."""

    def __init__(
        self,
        runtime_factory: Callable[..., Any] = Runtime,
    ) -> None:
        """Initialize an inactive browser worker."""
        self._runtime_factory = runtime_factory
        self._executor: ThreadPoolExecutor | None = None
        self._runtime: Any | None = None
        self._current_profile: str | None = None
        self._requested_profile: str | None = None
        self._is_running = False
        self._lock = RLock()

    @property
    def current_profile(self) -> str | None:
        """Return the profile owned by the active runtime."""
        with self._lock:
            return self._current_profile

    @property
    def is_running(self) -> bool:
        """Return whether the browser runtime is active."""
        with self._lock:
            return self._is_running

    def _ensure_executor(self) -> ThreadPoolExecutor:
        """Create the single owner thread when needed."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="cnki-browser",
            )
        return self._executor

    def _start_runtime(self, profile: str | None) -> Any:
        """Start or replace the runtime on the owner thread."""
        if self._runtime is not None:
            self._runtime.close()
            self._runtime = None
            self._is_running = False
            self._current_profile = None
            self._requested_profile = None

        runtime = self._runtime_factory(profile=profile)
        try:
            page = runtime.start()
        except Exception:
            runtime.close()
            raise

        self._runtime = runtime
        self._is_running = True
        self._current_profile = self._resolve_profile(runtime, profile)
        self._requested_profile = profile
        return page

    @staticmethod
    def _resolve_profile(runtime: Any, requested: str | None) -> str | None:
        """Resolve the runtime profile without requiring one concrete runtime type."""
        current_profile = getattr(runtime, "current_profile", None)
        if isinstance(current_profile, str):
            return current_profile
        runtime_profile = getattr(runtime, "profile", None)
        if isinstance(runtime_profile, str):
            return runtime_profile
        return requested

    def start(self, profile: str | None = None) -> Any:
        """Start the browser, reusing it when the profile is unchanged."""
        with self._lock:
            executor = self._ensure_executor()
            if self._is_running and self._requested_profile == profile:
                if self._runtime is None:
                    raise RuntimeError("browser worker state is inconsistent")
                return executor.submit(self._runtime.get_page).result()

            return executor.submit(self._start_runtime, profile).result()

    def _invoke(self, operation: Callable[[Any], ResultT]) -> ResultT:
        """Invoke a browser operation on the owner thread."""
        if self._runtime is None:
            raise LoginRequired("please call login before using browser tools")
        return operation(self._runtime.get_page())

    def submit(self, operation: Callable[[Any], ResultT]) -> Future[ResultT]:
        """Queue a browser operation on the owner thread."""
        with self._lock:
            if not self._is_running or self._runtime is None:
                raise LoginRequired("please call login before using browser tools")
            executor = self._ensure_executor()
            return executor.submit(self._invoke, operation)

    def call(self, operation: Callable[[Any], ResultT]) -> ResultT:
        """Run a browser operation synchronously on the owner thread."""
        return self.submit(operation).result()

    def _close_runtime(self) -> None:
        """Close the runtime on its owner thread."""
        if self._runtime is not None:
            self._runtime.close()
        self._runtime = None
        self._current_profile = None
        self._requested_profile = None
        self._is_running = False

    def close(self) -> None:
        """Close the active runtime and release its owner thread."""
        with self._lock:
            executor = self._executor
            if executor is None:
                self._runtime = None
                self._current_profile = None
                self._requested_profile = None
                self._is_running = False
                return

            executor.submit(self._close_runtime).result()
            executor.shutdown(wait=True)
            self._executor = None

    def refresh_browser(self) -> dict[str, bool | str]:
        """Return the placeholder result for future browser recovery."""
        return {"success": False, "error": "not implemented"}


__all__ = ["BrowserWorker"]
