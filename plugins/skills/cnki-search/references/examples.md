# 调用示例

示例展示参数形状与操作顺序，示例词语不表示已验证存在相应文章。实际调用以当前工具 schema 和返回数据为准。

## 主题探索后取详情

调用 `easy-search`：

```json
{"keywords":"数字经济 性别工资差距","limit":10,"sort_by":"relevance"}
```

对需要摘要的结果调用 `get-info-from-url`：

```json
{"url":"<刚才搜索返回的真实 url>"}
```

CLI 对应操作：

```bash
cnki-mcp tool search "数字经济 性别工资差距" --limit 10 --sort-by relevance
cnki-mcp tool info --title "<实际返回的篇名>" --author "<实际作者>" --source "<实际来源>"
```

CLI 搜索没有 URL；`info --title` 返回匹配对象。`is_unique=true` 且 `article` 非空时按唯一匹配处理，否则检查 `candidates` 并补充真实年份等题录。

## 篇名、作者、年份范围和 CSSCI

调用 `advanced-search`：

```json
{
  "title": "平台经济",
  "author": "张三",
  "year_from": 2015,
  "year_to": 2024,
  "document_type": "学术期刊",
  "source_types": ["CSSCI"],
  "sort_by": "citation",
  "limit": 10
}
```

这是 2015—2024 年的示例。用户说“2015 年以来”时，结束年份取执行任务时的当前年，不能固定为 2024 或省略 `year_to`。无结果时先报告该组合，再有依据地调整。

## 作者择一、第一作者与原始表达式

```bash
cnki-mcp tool search --advanced "TI='平台经济' and (AU='张三' or AU='李四')" --year-from 2015 --year-to 2024 --source-type CSSCI --limit 10
cnki-mcp tool search --advanced "TI='平台经济' and FI='张三'" --limit 10
```

第一条表示作者择一，第二条要求张三为第一作者。无本机 CLI / Python 且 MCP 不支持原始式时，读 `explore-cnki-view` 操作网页专业检索，或说明能力缺口，不假造 MCP 参数或把 `FI` 降为 `AU`。

Python 示例保存为临时脚本后用 `uv run <脚本路径>` 执行：

```python
from cnki_mcp import CnkiClient

client = CnkiClient()
results = client.search(
    "TI='平台经济' and (AU='张三' or AU='李四')",
    year_from=2015,
    year_to=2024,
    limit=10,
    sort_by="citation",
)
for result in results:
    print(result.title, result.authors, result.journal, result.date, result.url)
```

`client.search_basic("词语")` 执行普通一站式检索；`client.search("表达式")` 执行专业检索，裸文本传给后者会作为篇名处理。换用 Python 不能绕过登录、限速或页面解析问题。

## 已知题录直接取详情

调用 `get-info-by-detail`：

```json
{
  "title": "<用户给出的完整篇名>",
  "authors": ["<已知作者>"],
  "year": 2024,
  "journal": "<已知期刊>",
  "limit": 3
}
```

删去未知条件，年份也要来自实际题录。返回列表逐篇核对，失败条目记录其 `error`。这里没有 CLI 匹配对象的 `is_unique`。

## 期刊某一期目录

先调用 `search-issn`：

```json
{"journal":"经济研究"}
```

返回的是“期刊名称 → ISSN”的字典。先从候选中确认目标期刊，再调用 `list-journal`：

```json
{"issn":"<目标期刊名称对应的 ISSN 值>","year":2024,"vol":3}
```

`vol=3` 是第 3 期。整理 `articles` 即可，不重复逐篇取相同详情；分别用返回的 `volume` / `issue` 表示卷、期。

## 登录问题

stdio 通过 `profile://list` 确认已有 profile，调用 `login`：

```json
{"profile":"<实际 profile 名称>"}
```

HTTP / SSE 没有这个工具，由服务所在机器处理认证。本机首次使用 `cnki-mcp init -p <profile>` 会弹出窗口并设默认 profile；已有 profile 可用 `cnki-mcp login -p <profile>`。登录、机构认证和验证码由用户亲自完成，不读取凭据或替用户填写邮箱。
