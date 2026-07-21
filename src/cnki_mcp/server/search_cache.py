#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : server/search_cache.py

"""Short-lived in-memory cache for MCP search results."""

from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..core.models import SearchResult

DEFAULT_TTL_SECONDS = 600.0
DEFAULT_MAX_ENTRIES = 1_000


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    """Store a search result together with its insertion timestamp."""

    result: SearchResult
    inserted_at: float


def _normalize_url(value: str) -> str:
    """Return a stable cache key for a URL or article identifier."""
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if not parsed.scheme or not parsed.netloc:
        return candidate

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    port = parsed.port
    include_port = port is not None and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    )
    user_info = ""
    if parsed.username is not None:
        user_info = parsed.username
        if parsed.password is not None:
            user_info += f":{parsed.password}"
        user_info += "@"
    netloc = f"{user_info}{hostname}"
    if include_port:
        netloc += f":{port}"

    query_items = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    query = urlencode(query_items, doseq=True)
    return urlunsplit((scheme, netloc, parsed.path, query, ""))


class SearchResultCache:
    """Cache search results for a bounded period and entry count."""

    def __init__(
        self,
        *,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        """Initialize the cache with an injectable monotonic clock."""
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than zero")

        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = RLock()

    def put(self, results: Iterable[SearchResult]) -> None:
        """Add search results and evict expired or oldest entries."""
        with self._lock:
            now = self._clock()
            self._remove_expired(now)
            for result in results:
                identifier = result.url or result.article_id
                key = _normalize_url(identifier)
                if not key:
                    continue
                self._entries.pop(key, None)
                self._entries[key] = _CacheEntry(result=result, inserted_at=now)
                while len(self._entries) > self._max_entries:
                    self._entries.popitem(last=False)

    def get(self, url: str) -> SearchResult | None:
        """Return a cached result when it exists and has not expired."""
        key = _normalize_url(url)
        if not key:
            return None

        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if self._is_expired(entry, self._clock()):
                del self._entries[key]
                return None
            return entry.result

    def clear(self) -> None:
        """Remove all cached results."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        """Return the number of unexpired cached results."""
        with self._lock:
            self._remove_expired(self._clock())
            return len(self._entries)

    def _is_expired(self, entry: _CacheEntry, now: float) -> bool:
        """Return whether an entry has reached the configured TTL."""
        return now - entry.inserted_at >= self._ttl_seconds

    def _remove_expired(self, now: float) -> None:
        """Remove every entry whose TTL has elapsed."""
        expired_keys = [
            key
            for key, entry in self._entries.items()
            if self._is_expired(entry, now)
        ]
        for key in expired_keys:
            del self._entries[key]


__all__ = ["SearchResultCache"]
