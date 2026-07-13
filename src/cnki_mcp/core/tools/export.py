#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/tools/export.py

"""Retrieve citation metadata from the CNKI export endpoint."""

import html
import re
from typing import Any

from ..auth import ensure_login
from ..config import PAGE_LOAD_TIMEOUT_SECONDS
from ..exceptions import MetadataError
from ..models import SearchResult
from ..ratelimit import rate_limited
from ..runtime import Runtime

CNKI_EXPORT_URL = "https://kns.cnki.net/dm8/API/GetExport"
CNKI_EXPORT_PLATFORM = "NZKPT"
CNKI_EXPORT_DISPLAY_MODE = "GBTREFER,elearning,EndNote"
DEFAULT_REFERER = "https://kns.cnki.net/kns8s/defaultresult/index"
_LINE_BREAK_PATTERN = re.compile(r"<br\s*/?>", flags=re.I)


def build_export_form(search_result: SearchResult) -> dict[str, str]:
    """Build the verified CNKI export request form."""
    export_id = (search_result.export_id or "").strip()
    if not export_id:
        raise MetadataError("CNKI search result has no export identifier")
    return {
        "filename": export_id,
        "uniplatform": CNKI_EXPORT_PLATFORM,
        "displaymode": CNKI_EXPORT_DISPLAY_MODE,
    }


def extract_endnote_text(payload: object) -> str:
    """Extract and normalize EndNote text from a CNKI export response."""
    if not isinstance(payload, dict) or payload.get("code") != 1:
        raise MetadataError("CNKI citation export was rejected")
    records = payload.get("data")
    if not isinstance(records, list):
        raise MetadataError("CNKI citation export contains no records")

    for record in records:
        if not isinstance(record, dict) or record.get("key") != "EndNote":
            continue
        values = record.get("value")
        if not isinstance(values, list) or not values:
            break
        value = values[0]
        if not isinstance(value, str) or not value.strip():
            break
        with_line_breaks = _LINE_BREAK_PATTERN.sub("\n", value)
        return html.unescape(with_line_breaks).strip()
    raise MetadataError("CNKI citation export contains no EndNote record")


def _request_headers(search_result: SearchResult) -> dict[str, str]:
    """Build request headers without exposing stored session data."""
    referer = search_result.url or DEFAULT_REFERER
    return {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.cnki.net",
        "Referer": referer,
    }


@rate_limited(profile=None)
def run(
    search_result: SearchResult,
    *,
    profile: str | None = None,
) -> str:
    """Fetch one EndNote record for a CNKI search result."""
    try:
        form = build_export_form(search_result)
        ensure_login(profile=profile)
        with Runtime(profile=profile) as runtime:
            page = runtime.get_page()
            response = page.request.post(
                CNKI_EXPORT_URL,
                form=form,
                headers=_request_headers(search_result),
                timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000,
            )
            if response.status == 403:
                raise MetadataError(
                    "CNKI citation export requires manual security verification"
                )
            if response.status != 200:
                raise MetadataError(
                    f"CNKI citation export returned HTTP {response.status}"
                )
            payload: Any = response.json()
            return extract_endnote_text(payload)
    except MetadataError:
        raise
    except Exception as exc:
        raise MetadataError(f"CNKI citation export failed: {exc}") from exc


__all__ = [
    "CNKI_EXPORT_URL",
    "build_export_form",
    "extract_endnote_text",
    "run",
]
