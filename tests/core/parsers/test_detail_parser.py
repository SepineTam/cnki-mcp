#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/parsers/test_detail_parser.py

"""Tests for core/parsers/detail_parser.py."""

import pytest

from cnki_mcp.core.exceptions import ParseError
from cnki_mcp.core.models import Article
from cnki_mcp.core.parsers.detail_parser import (
    _parse_year,
    parse_html,
)


def test_parse_year_extracts_four_digit_year() -> None:
    """_parse_year extracts the first four-digit year."""
    assert _parse_year("2024年") == 2024
    assert _parse_year("Published 2023/05") == 2023
    assert _parse_year(None) is None
    assert _parse_year("no year") is None


def test_parse_html_returns_article() -> None:
    """parse_html returns an Article object."""
    html = """
    <html>
      <body>
        <h1 class="title">Article Title</h1>
        <span class="author">Author A</span>
        <span class="author">Author B</span>
        <div class="abstract">This is the abstract.</div>
        <span class="year">2024</span>
      </body>
    </html>
    """
    article = parse_html(html)
    assert isinstance(article, Article)
    assert article.title == "Article Title"


def test_parse_html_returns_kns_article_metadata() -> None:
    """parse_html extracts current KNS article detail metadata."""
    detail_url = (
        "https://kns.cnki.net/kcms2/article/abstract"
        "?v=encrypted&uniplatform=NZKPT&language=CHS"
    )
    html = """
    <html>
      <body>
        <div class="wxTitle">
          <h1>历史主动与历史耐心:中国式农业农村现代化的辩证逻辑</h1>
        </div>
        <div class="authors">
          <a>张三</a>
          <a>李四</a>
        </div>
        <div class="orgn">上海大学</div>
        <span id="ChDivSummary">摘要：本文讨论人工智能治理。</span>
        <p class="keywords">
          <a>人工智能</a>
          <a>数字经济</a>
        </p>
        <div class="sourinfo">
          <a>管理世界</a>
          <span>2026年</span>
        </div>
        <span class="doi">DOI：10.1234/example</span>
        <a class="download" href="https://bar.cnki.net/bar/download/order?id=x">
          下载
        </a>
      </body>
    </html>
    """
    article = parse_html(html, url=detail_url)
    assert article.article_id == detail_url
    assert article.title == "历史主动与历史耐心:中国式农业农村现代化的辩证逻辑"
    assert article.authors == ["张三", "李四"]
    assert article.institution == "上海大学"
    assert article.abstract == "本文讨论人工智能治理。"
    assert article.keywords == ["人工智能", "数字经济"]
    assert article.year == 2026
    assert article.source == "管理世界"
    assert article.doi == "10.1234/example"
    assert article.download_url is None


def test_parse_html_missing_required_fields_raises() -> None:
    """Missing title raises ParseError."""
    html = "<html><body></body></html>"
    with pytest.raises(ParseError):
        parse_html(html)
