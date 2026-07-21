#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/core/parsers/test_journal_parser.py

"""Tests for core/parsers/journal_parser.py."""

from playwright.sync_api import sync_playwright

from cnki_mcp.core.parsers import journal_parser


def test_parse_search_results_reads_name_url_and_journal_code() -> None:
    """Navi search cards expose a fresh URL and stable journal code."""
    html = """
    <ul>
      <li>
        <a title="世界经济" href="https://navi.cnki.net/knavi/detail?p=fresh">
          <img src="https://c61.cnki.net/cjfd/small/sjjj.jpg">
          <h1>世界经济</h1>
        </a>
      </li>
    </ul>
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.set_content(html)
            records = journal_parser.parse_search_results(page)
        finally:
            browser.close()

    assert len(records) == 1
    assert records[0].name == "世界经济"
    assert records[0].url.endswith("p=fresh")
    assert records[0].code == "SJJJ"


def test_parse_journal_record_reads_name_issn_and_stable_code() -> None:
    """The detail page exposes canonical name, ISSN, and pykm code."""
    html = """
    <input id="shareChName" value="经济学(季刊)">
    <input id="pykm" value="JJXU">
    <div>基本信息</div>
    <div>ISSN：2095-1086</div>
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.set_content(html)
            record = journal_parser.parse_journal_record(
                page,
                url="https://navi.cnki.net/knavi/detail?p=fresh",
            )
        finally:
            browser.close()

    assert record.name == "经济学(季刊)"
    assert record.issn == "2095-1086"
    assert record.code == "JJXU"


def test_parse_issue_html_reads_catalog_rows_and_total_count() -> None:
    """One issue response yields article candidates and its raw row count."""
    html = """
    <input id="articleCount" value="3">
    <dd class="row">
      <span class="name">
        <a href="https://kns.cnki.net/kcms2/article/abstract?v=one">Article 1</a>
        <b name="encrypt" id="SJJJ202601001"></b>
      </span>
      <span class="author" title="Author A;Author B;"></span>
      <span class="company" title="3-20"></span>
    </dd>
    <dd class="row">
      <span class="name">
        <a href="https://kns.cnki.net/kcms2/article/abstract?v=two">Article 2</a>
        <b name="encrypt" id="SJJJ202601002"></b>
      </span>
      <span class="author" title="Author C;"></span>
      <span class="company" title="21-40"></span>
    </dd>
    <dd class="row">
      <span class="name">
        <a href="https://kns.cnki.net/kcms2/article/abstract?v=notice">Notice</a>
        <b name="encrypt" id="SJJJ202601003"></b>
      </span>
      <span class="author" title=""></span>
      <span class="company" title="41"></span>
    </dd>
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            results, total_count = journal_parser.parse_issue_html(
                page,
                html,
                journal_name="世界经济",
                year=2026,
            )
        finally:
            browser.close()

    assert total_count == 3
    assert [result.title for result in results] == [
        "Article 1",
        "Article 2",
        "Notice",
    ]
    assert results[0].authors == ["Author A", "Author B"]
    assert results[0].article_id == "SJJJ202601001"
    assert results[0].url.endswith("v=one")
