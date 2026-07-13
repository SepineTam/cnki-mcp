from __future__ import annotations

import pytest

from cnki_mcp.core.exceptions import ParseError
from cnki_mcp.core.parsers.export_parser import parse


def test_parse_endnote_export() -> None:
    export_text = """%0 Journal Article
%T “无心插柳”——世界杯“爆冷获胜”的贸易创造
%A 袁晓燕
%A 翁士汉
%J 世界经济文汇
%D 2024
%V 4
%N 2
%P 1-18
%R 10.1234/example
%X 这是一段摘要。
%K 国际贸易
%K 世界杯; 爆冷获胜
%U https://kns.cnki.net/kcms2/article/abstract?v=example
"""

    article = parse(export_text)

    assert article.title == "“无心插柳”——世界杯“爆冷获胜”的贸易创造"
    assert article.authors == ["袁晓燕", "翁士汉"]
    assert article.source == "世界经济文汇"
    assert article.year == 2024
    assert article.volume == "4"
    assert article.issue == "2"
    assert article.pages == "1-18"
    assert article.doi == "10.1234/example"
    assert article.abstract == "这是一段摘要。"
    assert article.keywords == ["国际贸易", "世界杯", "爆冷获胜"]
    assert article.url == "https://kns.cnki.net/kcms2/article/abstract?v=example"
    assert article.download_url is None


def test_parse_refworks_export_with_continuation_lines() -> None:
    export_text = """RT Journal Article
T1 经济学研究“过度模型化”的误区及其纠正
A1 陆铭
JF 中国社会科学
YR 2026
VO 12
IS 2
SP 101
OP 120
DO 10.5678/example
AB 摘要的第一行
   摘要的第二行
K1 经济学; 研究方法
UL https://kns.cnki.net/kcms2/article/abstract?v=another
ER
"""

    article = parse(export_text)

    assert article.title == "经济学研究“过度模型化”的误区及其纠正"
    assert article.authors == ["陆铭"]
    assert article.source == "中国社会科学"
    assert article.year == 2026
    assert article.volume == "12"
    assert article.issue == "2"
    assert article.pages == "101-120"
    assert article.doi == "10.5678/example"
    assert article.abstract == "摘要的第一行 摘要的第二行"
    assert article.keywords == ["经济学", "研究方法"]
    assert article.url == "https://kns.cnki.net/kcms2/article/abstract?v=another"


@pytest.mark.parametrize(
    "export_text",
    [
        "",
        "%A 只有作者\n%D 2024",
        "T1    \nA1 陆铭\nER",
        "not a supported export format",
    ],
)
def test_parse_rejects_export_without_title(export_text: str) -> None:
    with pytest.raises(ParseError):
        parse(export_text)
