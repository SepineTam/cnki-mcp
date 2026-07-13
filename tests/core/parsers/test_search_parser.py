#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/parsers/test_search_parser.py

"""Tests for core/parsers/search_parser.py."""

import pytest

from cnki_mcp.core.exceptions import ParseError
from cnki_mcp.core.models import SearchResult
from cnki_mcp.core.parsers.search_parser import (
    _parse_citation_count,
    parse_html,
    parse_total_count,
)


def test_parse_citation_count_extracts_number() -> None:
    """_parse_citation_count pulls the first integer from text."""
    assert _parse_citation_count("被引量：123") == 123
    assert _parse_citation_count("Cited 45 times") == 45
    assert _parse_citation_count(None) is None
    assert _parse_citation_count("no number") is None


def test_parse_html_returns_search_results() -> None:
    """parse_html returns a list of SearchResult objects."""
    html = """
    <html>
      <body>
        <div class="result-list">
          <div class="result-item">
            <a class="title" href="/article/id1">Title One</a>
            <span class="author">Author A</span>
          </div>
          <div class="result-item">
            <a class="title" href="/article/id2">Title Two</a>
            <span class="author">Author B</span>
          </div>
        </div>
      </body>
    </html>
    """
    results = parse_html(html)
    assert isinstance(results, list)
    assert all(isinstance(r, SearchResult) for r in results)


def test_parse_html_returns_kns_table_results() -> None:
    """parse_html extracts current KNS table search results."""
    detail_url = (
        "https://kns.cnki.net/kcms2/article/abstract"
        "?v=encrypted&uniplatform=NZKPT&language=CHS"
    )
    html = f"""
    <html>
      <body>
        <div id="gridTable">
          <table class="result-table-list">
            <tbody>
              <tr>
                <td class="seq">
                  <input name="CookieName" value="encrypted-cid" />
                </td>
                <td class="name">
                  <a class="fz14 inline" href="{detail_url}">
                    以“<font color="red">人工智能</font>+”行动赋能新质生产力发展
                  </a>
                </td>
                <td class="author"><a>陈柳钦</a></td>
                <td class="source"><p><a>企业科技与发展</a></p></td>
                <td class="date">2026-07-09 11:46</td>
                <td class="quote">5</td>
                <td class="operat">
                  <a data-dbname="CJFDAUTO"
                     data-dbcode="CJFQ"
                     data-filename="QYKJ202607001"></a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </body>
    </html>
    """
    results = parse_html(html)
    assert len(results) == 1
    assert results[0].article_id == detail_url
    assert results[0].title == "以“人工智能+”行动赋能新质生产力发展"
    assert results[0].authors == ["陈柳钦"]
    assert results[0].year == 2026
    assert results[0].date == "2026-07-09"
    assert results[0].source == "企业科技与发展"
    assert results[0].citation_count == 5
    assert results[0].filename == "QYKJ202607001"
    assert results[0].dbcode == "CJFQ"
    assert results[0].dbname == "CJFDAUTO"
    assert results[0].export_id == "encrypted-cid"


def test_parse_html_empty_results() -> None:
    """parse_html returns an empty list when no results exist."""
    html = "<html><body></body></html>"
    results = parse_html(html)
    assert results == []


def test_parse_html_missing_required_fields_raises() -> None:
    """Missing article_id or title raises ParseError."""
    html = """
    <html><body>
      <div class="result-list">
        <div class="result-item"></div>
      </div>
    </body></html>
    """
    with pytest.raises(ParseError):
        parse_html(html)


def test_parse_total_count_returns_none_by_default() -> None:
    """parse_total_count defaults to None when not implemented."""
    page = object()
    assert parse_total_count(page) is None
