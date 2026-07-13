#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/retrieval/models.py

from dataclasses import dataclass, field

from ..models import Article, SearchResult


@dataclass
class CnkiQuery:
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    source: str | None = None
    document_type: str | None = None


@dataclass
class CnkiIdentifier:
    filename: str | None = None
    dbcode: str | None = None
    dbname: str | None = None
    url: str | None = None

    @property
    def stable_id(self) -> str | None:
        if not self.filename:
            return None

        filename = self.filename.strip()
        if not filename:
            return None

        database = self.dbcode or self.dbname
        if database and database.strip():
            return f"cnki:{database.strip()}:{filename}"
        return f"cnki:{filename}"


@dataclass
class CnkiCandidate:
    search_result: SearchResult
    total_score: float
    field_scores: dict[str, float] = field(default_factory=dict)
    mismatch_reasons: list[str] = field(default_factory=list)


@dataclass
class MetadataLookupResult:
    article: Article | None = None
    candidates: list[CnkiCandidate] = field(default_factory=list)
    selected_candidate: CnkiCandidate | None = None
    data_sources: list[str] = field(default_factory=list)
    is_unique: bool = False


__all__ = [
    "CnkiCandidate",
    "CnkiIdentifier",
    "CnkiQuery",
    "MetadataLookupResult",
]

