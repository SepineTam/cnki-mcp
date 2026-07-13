from __future__ import annotations

import pytest

from cnki_mcp.core.exceptions import MetadataError
from cnki_mcp.core.models import Article, SearchResult
from cnki_mcp.core.retrieval.models import CnkiQuery
from cnki_mcp.core.tools.metadata_lookup import (
    lookup,
    normalize_text,
    rank_candidates,
    score_authors,
    score_candidate_fields,
    score_text,
    select_unique_candidate,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "《无心插柳》——世界杯‘爆冷获胜’的贸易创造",
            "无心插柳世界杯爆冷获胜的贸易创造",
        ),
        ("  中国 社会科学\n", "中国社会科学"),
        ("ＡＢＣ，经济学！", "abc经济学"),
    ],
)
def test_normalize_text_ignores_spacing_punctuation_and_width(
    value: str,
    expected: str,
) -> None:
    assert normalize_text(value) == expected


def test_score_text_tolerates_quote_and_punctuation_differences() -> None:
    score = score_text(
        "“无心插柳”——世界杯“爆冷获胜”的贸易创造",
        "无心插柳：世界杯爆冷获胜的贸易创造",
    )

    assert score == 1.0


def test_score_authors_is_order_independent_and_penalizes_missing_names() -> None:
    assert score_authors(["袁晓燕", "翁士汉"], ["翁士汉", "袁晓燕"]) == 1.0
    assert score_authors(["袁晓燕", "翁士汉"], ["袁晓燕"]) < 1.0
    assert score_authors([], ["袁晓燕"]) == 0.0


def test_score_candidate_fields_prioritizes_title_and_supporting_fields() -> None:
    exact = score_candidate_fields(
        title="无心插柳——世界杯爆冷获胜的贸易创造",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
        candidate_title="无心插柳：世界杯“爆冷获胜”的贸易创造",
        candidate_authors=["翁士汉", "袁晓燕"],
        candidate_year=2024,
        candidate_source="世界经济文汇",
    )
    wrong_article = score_candidate_fields(
        title="无心插柳——世界杯爆冷获胜的贸易创造",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
        candidate_title="无心插柳：世界杯与国际传播",
        candidate_authors=["袁晓燕"],
        candidate_year=2023,
        candidate_source="新闻研究",
    )

    assert exact == 1.0
    assert wrong_article < exact


def test_score_candidate_fields_requires_title() -> None:
    with pytest.raises(ValueError, match="title"):
        score_candidate_fields(
            title="",
            authors=[],
            year=None,
            source=None,
            candidate_title="候选标题",
            candidate_authors=[],
            candidate_year=None,
            candidate_source=None,
        )


def test_rank_candidates_places_best_match_first() -> None:
    query = CnkiQuery(
        title="无心插柳——世界杯爆冷获胜的贸易创造",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
    )
    results = [
        SearchResult(
            article_id="wrong",
            title="世界杯与国际传播",
            authors=["袁晓燕"],
            year=2023,
            source="新闻研究",
        ),
        SearchResult(
            article_id="right",
            title="《无心插柳》：世界杯“爆冷获胜”的贸易创造",
            authors=["翁士汉", "袁晓燕"],
            year=2024,
            source="世界经济文汇",
        ),
    ]

    candidates = rank_candidates(query, results)

    assert candidates[0].search_result.article_id == "right"
    assert candidates[0].total_score == 1.0
    assert candidates[0].field_scores == {
        "title": 1.0,
        "authors": 1.0,
        "year": 1.0,
        "source": 1.0,
    }


def test_select_unique_candidate_rejects_near_tie() -> None:
    query = CnkiQuery(title="相同标题")
    candidates = rank_candidates(
        query,
        [
            SearchResult(article_id="first", title="相同标题"),
            SearchResult(article_id="second", title="相同标题"),
        ],
    )

    assert select_unique_candidate(candidates) is None


def test_lookup_fetches_detail_metadata_for_unique_candidate(monkeypatch) -> None:
    query = CnkiQuery(title="目标文章", authors=["作者甲"], year=2025)
    search_result = SearchResult(
        article_id="article-id",
        title="目标文章",
        authors=["作者甲"],
        year=2025,
        source="搜索来源",
        url="https://kns.cnki.net/current-result",
    )
    article = Article(
        article_id="article-id",
        title="详情标题",
        authors=["作者甲", "错误机构名称"],
        source="详情来源",
    )
    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.search.run",
        lambda *args, **kwargs: [search_result],
    )
    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.metadata.run",
        lambda *args, **kwargs: article,
    )

    result = lookup(query)

    assert result.article is not article
    assert result.article is not None
    assert result.article.title == "目标文章"
    assert result.article.authors == ["作者甲"]
    assert result.article.year == 2025
    assert result.article.source == "搜索来源"
    assert result.article.url == "https://kns.cnki.net/current-result"
    assert result.is_unique is True
    assert result.selected_candidate is result.candidates[0]
    assert result.data_sources == ["search", "detail"]


def test_lookup_passes_available_fields_to_search(monkeypatch) -> None:
    query = CnkiQuery(
        title="目标文章",
        authors=["作者甲", "作者乙"],
        year=2025,
        source="目标期刊",
        document_type="journal",
    )
    captured: dict[str, object] = {}

    def capture_search(search_query, **kwargs):
        captured["query"] = search_query
        captured.update(kwargs)
        return [
            SearchResult(
                article_id="first",
                title="目标文章",
                authors=["作者甲", "作者乙"],
                year=2025,
                source="目标期刊",
            ),
            SearchResult(
                article_id="second",
                title="目标文章",
                authors=["作者甲", "作者乙"],
                year=2025,
                source="目标期刊",
            ),
        ]

    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.search.run",
        capture_search,
    )

    def unexpected_metadata_call(*args, **kwargs):
        raise AssertionError("ambiguous results must not fetch metadata")

    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.metadata.run",
        unexpected_metadata_call,
    )

    result = lookup(query, profile="research-profile", limit=20)

    assert captured == {
        "query": query,
        "profile": "research-profile",
        "limit": 20,
    }
    assert captured["query"].authors == ["作者甲", "作者乙"]
    assert result.selected_candidate is None
    assert result.is_unique is False
    assert len(result.candidates) == 2


def test_lookup_fetches_and_parses_export_when_detail_fetch_fails(
    monkeypatch,
) -> None:
    query = CnkiQuery(title="目标文章", authors=["作者甲"], year=2025)
    search_result = SearchResult(
        article_id="article-id",
        title="目标文章",
        authors=["作者甲"],
        year=2025,
    )
    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.search.run",
        lambda *args, **kwargs: [search_result],
    )

    def fail_metadata(*args, **kwargs):
        raise MetadataError("detail unavailable")

    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.metadata.run",
        fail_metadata,
    )
    export_calls = []

    def fetch_export(result, *, profile):
        export_calls.append((result, profile))
        return "%0 Journal Article\n%T 目标文章\n%A 作者甲"

    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.export.run",
        fetch_export,
    )

    result = lookup(query, profile="research-profile")

    assert result.article is not None
    assert result.article.title == "目标文章"
    assert result.article.year == 2025
    assert result.data_sources == ["search", "export"]
    assert export_calls == [(search_result, "research-profile")]


def test_lookup_keeps_candidate_when_export_payload_is_invalid(monkeypatch) -> None:
    """An invalid fallback export does not discard the resolved candidate."""
    query = CnkiQuery(title="目标文章")
    search_result = SearchResult(article_id="article-id", title="目标文章")
    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.search.run",
        lambda *args, **kwargs: [search_result],
    )
    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.metadata.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(MetadataError("failed")),
    )

    result = lookup(query, export_text="invalid export")

    assert result.is_unique is True
    assert result.selected_candidate is result.candidates[0]
    assert result.article is None
    assert result.data_sources == ["search"]


def test_lookup_does_not_fetch_metadata_for_ambiguous_results(monkeypatch) -> None:
    query = CnkiQuery(title="同名文章")
    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.search.run",
        lambda *args, **kwargs: [
            SearchResult(article_id="first", title="同名文章"),
            SearchResult(article_id="second", title="同名文章"),
        ],
    )

    def unexpected_metadata_call(*args, **kwargs):
        raise AssertionError("ambiguous results must not fetch metadata")

    monkeypatch.setattr(
        "cnki_mcp.core.tools.metadata_lookup.metadata.run",
        unexpected_metadata_call,
    )

    result = lookup(query)

    assert result.article is None
    assert result.selected_candidate is None
    assert result.is_unique is False
    assert len(result.candidates) == 2
    assert result.data_sources == ["search"]
