#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/retrieval/test_models.py

from cnki_mcp.core.models import Article, SearchResult
from cnki_mcp.core.retrieval.models import (
    CnkiCandidate,
    CnkiIdentifier,
    CnkiQuery,
    MetadataLookupResult,
)


def test_cnki_query_only_requires_title() -> None:
    query = CnkiQuery(title="无心插柳")

    assert query.title == "无心插柳"
    assert query.authors == []
    assert query.year is None
    assert query.source is None
    assert query.document_type is None


def test_cnki_query_accepts_available_search_fields() -> None:
    query = CnkiQuery(
        title="无心插柳——世界杯“爆冷获胜”的贸易创造",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
        document_type="journal",
    )

    assert query.authors == ["袁晓燕", "翁士汉"]
    assert query.year == 2024
    assert query.source == "世界经济文汇"
    assert query.document_type == "journal"


def test_cnki_identifier_builds_stable_id_from_cnki_fields() -> None:
    identifier = CnkiIdentifier(
        filename="SJHJ202401001",
        dbcode="CJFD",
        dbname="CJFDLAST2024",
        url="https://kns.cnki.net/kcms2/article/abstract?v=temporary",
    )

    assert identifier.stable_id == "cnki:CJFD:SJHJ202401001"


def test_cnki_identifier_uses_dbname_when_dbcode_is_missing() -> None:
    identifier = CnkiIdentifier(filename="SJHJ202401001", dbname="CJFDLAST2024")

    assert identifier.stable_id == "cnki:CJFDLAST2024:SJHJ202401001"


def test_cnki_identifier_uses_filename_without_database_context() -> None:
    identifier = CnkiIdentifier(filename="SJHJ202401001")

    assert identifier.stable_id == "cnki:SJHJ202401001"


def test_cnki_identifier_does_not_treat_url_as_stable() -> None:
    identifier = CnkiIdentifier(url="https://kns.cnki.net/temporary")

    assert identifier.stable_id is None


def test_candidate_and_lookup_result_keep_matching_evidence() -> None:
    search_result = SearchResult(
        article_id="SJHJ202401001",
        title="无心插柳",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
    )
    candidate = CnkiCandidate(
        search_result=search_result,
        total_score=0.98,
        field_scores={"title": 1.0, "authors": 1.0, "source": 0.9},
        mismatch_reasons=[],
    )
    article = Article(article_id="SJHJ202401001", title="无心插柳")

    lookup_result = MetadataLookupResult(
        article=article,
        candidates=[candidate],
        selected_candidate=candidate,
        data_sources=["detail_page"],
        is_unique=True,
    )

    assert lookup_result.article is article
    assert lookup_result.candidates == [candidate]
    assert lookup_result.selected_candidate is candidate
    assert lookup_result.data_sources == ["detail_page"]
    assert lookup_result.is_unique is True


def test_lookup_result_defaults_to_no_match() -> None:
    lookup_result = MetadataLookupResult()

    assert lookup_result.article is None
    assert lookup_result.candidates == []
    assert lookup_result.selected_candidate is None
    assert lookup_result.data_sources == []
    assert lookup_result.is_unique is False

