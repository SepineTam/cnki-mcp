#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : core/retrieval/__init__.py

from .base import CnkiRetrievalService
from .models import (
    CnkiCandidate,
    CnkiIdentifier,
    CnkiQuery,
    MetadataLookupResult,
)

__all__ = [
    "CnkiCandidate",
    "CnkiIdentifier",
    "CnkiQuery",
    "CnkiRetrievalService",
    "MetadataLookupResult",
]

