#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/retrieval/base.py

import unicodedata
from abc import ABC, abstractmethod

from .models import CnkiQuery, MetadataLookupResult


class CnkiRetrievalService(ABC):
    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return "".join(
            character
            for character in normalized
            if not character.isspace()
            and not unicodedata.category(character).startswith(("P", "S"))
        )

    @classmethod
    def normalize_title(cls, title: str) -> str:
        return cls._normalize_text(title)

    @classmethod
    def normalize_author(cls, author: str) -> str:
        return cls._normalize_text(author)

    @classmethod
    def normalize_authors(cls, authors: list[str]) -> list[str]:
        normalized_authors = [cls.normalize_author(author) for author in authors]
        return [author for author in normalized_authors if author]

    @classmethod
    def normalize_source(cls, source: str) -> str:
        return cls._normalize_text(source)

    @abstractmethod
    def execute(
        self,
        query: CnkiQuery,
        profile: str = "profile1",
    ) -> MetadataLookupResult:
        raise NotImplementedError


__all__ = ["CnkiRetrievalService"]
