#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/retrieval/test_base.py

from cnki_mcp.core.retrieval.base import CnkiRetrievalService
from cnki_mcp.core.retrieval.models import CnkiQuery, MetadataLookupResult


class StubRetrievalService(CnkiRetrievalService):
    def execute(
        self,
        query: CnkiQuery,
        profile: str = "profile1",
    ) -> MetadataLookupResult:
        return MetadataLookupResult(data_sources=[profile])


def test_normalize_title_removes_spacing_and_punctuation() -> None:
    normalized = StubRetrievalService.normalize_title(
        " 无心插柳——世界杯 “爆冷获胜” 的贸易创造 "
    )

    assert normalized == "无心插柳世界杯爆冷获胜的贸易创造"


def test_normalize_author_handles_chinese_and_latin_names() -> None:
    assert StubRetrievalService.normalize_author("陆 铭") == "陆铭"
    assert StubRetrievalService.normalize_author(" John Smith ") == "johnsmith"


def test_normalize_authors_discards_empty_values() -> None:
    normalized = StubRetrievalService.normalize_authors(["袁 晓燕", "", " 翁士汉 "])

    assert normalized == ["袁晓燕", "翁士汉"]


def test_normalize_source_removes_cnki_display_wrappers() -> None:
    assert StubRetrievalService.normalize_source("《中国社会科学》") == "中国社会科学"
    assert StubRetrievalService.normalize_source(" WORLD ECONOMY ") == "worldeconomy"


def test_concrete_service_implements_execute_contract() -> None:
    result = StubRetrievalService().execute(CnkiQuery(title="测试"), profile="school")

    assert result.data_sources == ["school"]

