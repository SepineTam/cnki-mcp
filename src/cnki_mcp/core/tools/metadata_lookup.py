#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/tools/metadata_lookup.py

"""Match known citation details against CNKI search candidates."""

from dataclasses import replace
from difflib import SequenceMatcher

from ..exceptions import MetadataError, ParseError
from ..models import Article, SearchResult
from ..parsers.export_parser import parse as parse_export
from ..retrieval.base import CnkiRetrievalService
from ..retrieval.models import CnkiCandidate, CnkiQuery, MetadataLookupResult
from . import export, metadata, search

TITLE_WEIGHT = 0.65
AUTHOR_WEIGHT = 0.15
YEAR_WEIGHT = 0.1
SOURCE_WEIGHT = 0.1
DEFAULT_MATCH_THRESHOLD = 0.86
DEFAULT_MINIMUM_LEAD = 0.08


def normalize_text(value: str) -> str:
    """Normalize text for tolerant citation matching."""
    return CnkiRetrievalService._normalize_text(value)


def score_text(expected: str | None, actual: str | None) -> float:
    """Return normalized text similarity in the inclusive range zero to one."""
    if not expected or not actual:
        return 0.0
    expected_text = normalize_text(expected)
    actual_text = normalize_text(actual)
    if not expected_text or not actual_text:
        return 0.0
    return SequenceMatcher(None, expected_text, actual_text).ratio()


def score_authors(expected: list[str], actual: list[str]) -> float:
    """Score author overlap without depending on author order."""
    expected_names = {normalize_text(author) for author in expected if author.strip()}
    actual_names = {normalize_text(author) for author in actual if author.strip()}
    expected_names.discard("")
    actual_names.discard("")
    if not expected_names or not actual_names:
        return 0.0
    overlap = len(expected_names & actual_names)
    return 2 * overlap / (len(expected_names) + len(actual_names))


def score_candidate_fields(
    *,
    title: str,
    authors: list[str],
    year: int | None,
    source: str | None,
    candidate_title: str,
    candidate_authors: list[str],
    candidate_year: int | None,
    candidate_source: str | None,
) -> float:
    """Score a CNKI candidate using title and available supporting fields."""
    if not title.strip():
        raise ValueError("title is required for metadata lookup")

    weighted_scores = [(TITLE_WEIGHT, score_text(title, candidate_title))]
    if authors:
        weighted_scores.append(
            (AUTHOR_WEIGHT, score_authors(authors, candidate_authors))
        )
    if year is not None:
        weighted_scores.append(
            (YEAR_WEIGHT, float(year == candidate_year))
        )
    if source:
        weighted_scores.append(
            (SOURCE_WEIGHT, score_text(source, candidate_source))
        )

    total_weight = sum(weight for weight, _ in weighted_scores)
    score = sum(weight * value for weight, value in weighted_scores) / total_weight
    return round(score, 6)


def _field_scores(
    query: CnkiQuery,
    search_result: SearchResult,
) -> dict[str, float]:
    """Return individual scores for fields supplied by the query."""
    scores = {"title": score_text(query.title, search_result.title)}
    if query.authors:
        scores["authors"] = score_authors(query.authors, search_result.authors)
    if query.year is not None:
        scores["year"] = float(query.year == search_result.year)
    if query.source:
        scores["source"] = score_text(query.source, search_result.source)
    return scores


def _mismatch_reasons(
    query: CnkiQuery,
    search_result: SearchResult,
    field_scores: dict[str, float],
) -> list[str]:
    """Describe material differences useful for caller review."""
    reasons = []
    if field_scores["title"] < 0.85:
        reasons.append("title differs")
    if query.authors and field_scores.get("authors", 0.0) < 0.5:
        reasons.append("authors differ")
    if query.year is not None and query.year != search_result.year:
        reasons.append("year differs")
    if query.source and field_scores.get("source", 0.0) < 0.75:
        reasons.append("source differs")
    return reasons


def rank_candidates(
    query: CnkiQuery,
    search_results: list[SearchResult],
) -> list[CnkiCandidate]:
    """Score CNKI search results and return the strongest matches first."""
    if not query.title.strip():
        raise ValueError("title is required for metadata lookup")

    candidates = []
    for search_result in search_results:
        field_scores = _field_scores(query, search_result)
        total_score = score_candidate_fields(
            title=query.title,
            authors=query.authors,
            year=query.year,
            source=query.source,
            candidate_title=search_result.title,
            candidate_authors=search_result.authors,
            candidate_year=search_result.year,
            candidate_source=search_result.source,
        )
        candidates.append(
            CnkiCandidate(
                search_result=search_result,
                total_score=total_score,
                field_scores=field_scores,
                mismatch_reasons=_mismatch_reasons(
                    query,
                    search_result,
                    field_scores,
                ),
            )
        )
    return sorted(candidates, key=lambda candidate: candidate.total_score, reverse=True)


def select_unique_candidate(
    candidates: list[CnkiCandidate],
    *,
    match_threshold: float = DEFAULT_MATCH_THRESHOLD,
    minimum_lead: float = DEFAULT_MINIMUM_LEAD,
) -> CnkiCandidate | None:
    """Select only a strong candidate that clearly leads every alternative."""
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda candidate: candidate.total_score,
        reverse=True,
    )
    strongest = ranked[0]
    if strongest.total_score < match_threshold:
        return None
    if len(ranked) > 1:
        lead = strongest.total_score - ranked[1].total_score
        if lead < minimum_lead:
            return None
    return strongest


def merge_article_fields(
    article: Article,
    search_result: SearchResult,
) -> Article:
    """Merge identity fields from the uniquely selected search result."""
    return replace(
        article,
        title=search_result.title or article.title,
        authors=list(search_result.authors) or article.authors,
        year=search_result.year if search_result.year is not None else article.year,
        source=search_result.source or article.source,
        url=article.url or search_result.url,
    )


def lookup(
    query: CnkiQuery,
    *,
    profile: str = "profile1",
    limit: int = 10,
    match_threshold: float = DEFAULT_MATCH_THRESHOLD,
    minimum_lead: float = DEFAULT_MINIMUM_LEAD,
    export_text: str | None = None,
) -> MetadataLookupResult:
    """Search CNKI, resolve one clear match, and retrieve its metadata."""
    if not query.title.strip():
        raise ValueError("title is required for metadata lookup")

    search_results = search.run(
        query,
        profile=profile,
        limit=limit,
    )
    candidates = rank_candidates(query, search_results)
    selected_candidate = select_unique_candidate(
        candidates,
        match_threshold=match_threshold,
        minimum_lead=minimum_lead,
    )
    result = MetadataLookupResult(candidates=candidates, data_sources=["search"])
    if selected_candidate is None:
        return result

    result.selected_candidate = selected_candidate
    result.is_unique = True
    try:
        article = metadata.run(
            selected_candidate.search_result.article_id,
            profile=profile,
        )
        result.article = merge_article_fields(
            article,
            selected_candidate.search_result,
        )
        result.data_sources.append("detail")
    except MetadataError:
        try:
            citation_text = export_text or export.run(
                selected_candidate.search_result,
                profile=profile,
            )
            result.article = merge_article_fields(
                parse_export(citation_text),
                selected_candidate.search_result,
            )
            result.data_sources.append("export")
        except (MetadataError, ParseError):
            pass
    return result


class MetadataLookupService(CnkiRetrievalService):
    """CNKI-specific retrieval service backed by search and detail metadata."""

    def execute(
        self,
        query: CnkiQuery,
        profile: str = "profile1",
    ) -> MetadataLookupResult:
        """Execute a metadata lookup through the shared service interface."""
        return lookup(query, profile=profile)


__all__ = [
    "MetadataLookupService",
    "lookup",
    "merge_article_fields",
    "normalize_text",
    "rank_candidates",
    "score_authors",
    "score_candidate_fields",
    "score_text",
    "select_unique_candidate",
]
