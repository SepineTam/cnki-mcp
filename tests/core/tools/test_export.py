#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/tools/test_export.py

"""Tests for the CNKI citation export operation."""

from unittest.mock import MagicMock, patch

import pytest

from cnki_mcp.core.exceptions import MetadataError
from cnki_mcp.core.models import SearchResult
from cnki_mcp.core.tools import export


def test_build_export_form_uses_search_result_export_id() -> None:
    search_result = SearchResult(
        article_id="article-id",
        title="目标文章",
        export_id="dynamic-export-id",
    )

    assert export.build_export_form(search_result) == {
        "filename": "dynamic-export-id",
        "uniplatform": "NZKPT",
        "displaymode": "GBTREFER,elearning,EndNote",
    }


def test_build_export_form_requires_export_id() -> None:
    search_result = SearchResult(article_id="article-id", title="目标文章")

    with pytest.raises(MetadataError, match="export identifier"):
        export.build_export_form(search_result)


def test_extract_endnote_text_uses_verified_response_shape() -> None:
    payload = {
        "code": 1,
        "data": [
            {"key": "GB/T 7714-2025 格式引文", "value": ["ignored"]},
            {
                "key": "EndNote",
                "value": [
                    "%0 Journal Article<br>%A 袁晓燕<br/>%A 翁士汉"
                    "<BR />%T 无心插柳&amp;贸易创造"
                ],
            },
        ],
    }

    assert export.extract_endnote_text(payload) == (
        "%0 Journal Article\n%A 袁晓燕\n%A 翁士汉\n%T 无心插柳&贸易创造"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"code": 0, "data": []},
        {"code": 1, "data": []},
        {"code": 1, "data": [{"key": "EndNote", "value": []}]},
    ],
)
def test_extract_endnote_text_rejects_incomplete_response(payload) -> None:
    with pytest.raises(MetadataError):
        export.extract_endnote_text(payload)


@patch("cnki_mcp.core.tools.export.ensure_login")
@patch("cnki_mcp.core.tools.export.Runtime")
def test_run_posts_verified_form_once(
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    search_result = SearchResult(
        article_id="article-id",
        title="目标文章",
        url="https://kns.cnki.net/kcms2/article/abstract?v=current",
        export_id="dynamic-export-id",
    )
    mock_response = MagicMock(status=200)
    mock_response.json.return_value = {
        "code": 1,
        "data": [
            {"key": "EndNote", "value": ["%0 Journal Article<br>%T 目标文章"]}
        ],
    }
    mock_page = MagicMock()
    mock_page.request.post.return_value = mock_response
    mock_runtime = mock_runtime_cls.return_value.__enter__.return_value
    mock_runtime.get_page.return_value = mock_page

    export_text = export.run.__wrapped__(search_result, profile="profile1")

    assert export_text == "%0 Journal Article\n%T 目标文章"
    mock_ensure_login.assert_called_once_with(profile="profile1")
    mock_page.request.post.assert_called_once()
    request_args = mock_page.request.post.call_args
    assert request_args.args == (export.CNKI_EXPORT_URL,)
    assert request_args.kwargs["form"] == {
        "filename": "dynamic-export-id",
        "uniplatform": "NZKPT",
        "displaymode": "GBTREFER,elearning,EndNote",
    }
    assert request_args.kwargs["headers"]["Referer"] == search_result.url


@patch("cnki_mcp.core.tools.export.ensure_login")
@patch("cnki_mcp.core.tools.export.Runtime")
def test_run_does_not_retry_security_verification(
    mock_runtime_cls: MagicMock,
    mock_ensure_login: MagicMock,
) -> None:
    search_result = SearchResult(
        article_id="article-id",
        title="目标文章",
        export_id="dynamic-export-id",
    )
    mock_response = MagicMock(status=403)
    mock_page = MagicMock()
    mock_page.request.post.return_value = mock_response
    mock_runtime = mock_runtime_cls.return_value.__enter__.return_value
    mock_runtime.get_page.return_value = mock_page

    with pytest.raises(MetadataError, match="security verification"):
        export.run.__wrapped__(search_result)

    mock_page.request.post.assert_called_once()
