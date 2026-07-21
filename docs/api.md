# Python API 与专业检索式

## 搜索接口

Python 调用方式：

```python
from cnki_mcp import CnkiClient

with CnkiClient(profile="profile1") as client:
    results = client.search(
        "TI='生态' and KY='生态文明'",
        sort_by="date",
    )
```

`CnkiClient.search(query)` 的 `query` 推荐使用知网专业检索式。为兼容已有
调用，也可以直接传入普通文章标题，程序会按篇名检索。

所有搜索都会进入知网专业检索页。年份范围、期刊、作者、作者单位、文献类型和
来源类别等附加条件也在专业检索流程中处理，不再使用一框式检索作为备用路线。

搜索支持以下基础参数：

| 参数 | 用途 |
| --- | --- |
| `query` | 专业检索式，或一个普通文章标题 |
| `limit` | 最多返回多少条结果 |
| `sort_by` | 排序方式，可选 `relevance`、`date`、`citation`、`comprehensive` |
| `year_from` / `year_to` | 发表年份范围 |
| `journal` | 期刊或文献来源 |
| `document_type` | 文献类型，例如 `journal` |
| `source_types` | 来源类别，例如 `CSSCI`、`SCI` |
| `author` | 作者 |
| `institution` | 作者单位 |

CLI 的搜索结果保持精简，每条记录有四项：

```json
[
  {
    "title": "文章标题",
    "authors": ["作者甲", "作者乙"],
    "journal": "期刊名称",
    "date": "2026-07-13"
  }
]
```

`date` 优先使用完整的 `yyyy-mm-dd`，知网页面只提供年份时则返回 `yyyy`。
搜索结果用于浏览和筛选，摘要、关键词、DOI 等详细信息由 `info` 命令返回。
MCP 搜索结果会额外返回 `url`，供 `get-info-from-url` 继续读取详情。

## 可检索字段

| 字段 | 含义 | 字段 | 含义 |
| --- | --- | --- | --- |
| `SU` | 主题 | `TKA` | 篇关摘 |
| `KY` | 关键词 | `TI` | 篇名 |
| `FT` | 全文 | `AU` | 作者 |
| `FI` | 第一作者 | `RP` | 通讯作者 |
| `AF` | 作者单位 | `FU` | 基金 |
| `AB` | 摘要 | `CO` | 小标题 |
| `RF` | 参考文献 | `CLC` | 分类号 |
| `LY` | 文献来源 | `DOI` | DOI |
| `CF` | 被引频次 | | |

完整写法为：

```text
SU=主题, TKA=篇关摘, KY=关键词, TI=篇名, FT=全文, AU=作者,
FI=第一作者, RP=通讯作者, AF=作者单位, FU=基金, AB=摘要,
CO=小标题, RF=参考文献, CLC=分类号, LY=文献来源, DOI=DOI,
CF=被引频次
```

## 示例

1. `TI='生态' and KY='生态文明' and (AU % '陈' + '王')`

   检索篇名包括“生态”、关键词包括“生态文明”，且作者为“陈”姓或“王”姓
   的文章。

2. `SU='北京' * '奥运' and FT='环境保护'`

   检索主题同时包括“北京”和“奥运”，且全文包括“环境保护”的信息。

3. `SU=('经济发展' + '可持续发展') * '转变' - '泡沫'`

   检索与“经济发展”或“可持续发展”有关的“转变”信息，并排除与“泡沫”
   有关的内容。

## CLI

项目只提供一个 `cnki-mcp` 命令。直接运行会启动默认 HTTP MCP Server：

```bash
uv run cnki-mcp
uv run cnki-mcp serve --transport http --host 127.0.0.1 --port 7788
```

默认地址为 `127.0.0.1:7788`。也可以明确选择 SSE 或 stdio：

```bash
uv run cnki-mcp serve --transport sse
uv run cnki-mcp serve --transport stdio
```

SSE 启动时会提示优先使用 HTTP。stdio 不接受 `--host` 和 `--port`。

普通文字默认使用一框式检索，专业检索式通过 `--advanced` 传入：

```bash
uv run cnki-mcp tool search "数字经济"
uv run cnki-mcp tool search --advanced "TI='生态' and KY='生态文明'"
```

直接解析知网详情页，或通过已知题录信息定位文章：

```bash
uv run cnki-mcp tool info "https://kns.cnki.net/kcms2/article/abstract?v=..."
uv run cnki-mcp tool info --title "无心插柳" --author "袁晓燕" --year 2024
```

登录与退出可以指定 profile：

```bash
uv run cnki-mcp login --profile school
uv run cnki-mcp logout --profile school
```

使用 `cnki-mcp --help`、`cnki-mcp --version` 或具体子命令的 `--help`
查看帮助。

## MCP 工具

推荐使用 HTTP。直接运行 `cnki-mcp` 即可启动 HTTP MCP Server，同时打开一个
持久浏览器。浏览器会在整个服务进程中复用，服务退出时随之关闭。

HTTP 和 SSE 提供四个工具：

- `easy-search(keywords, limit=10, sort_by=None)`：一框式检索。
- `advanced-search(...)`：用题名、作者、期刊、年份等结构化条件进行专业检索。
- `get-info-from-url(url)`：读取搜索结果 URL 对应的文章详情。
- `get-info-by-detail(...)`：用详细题录条件专业检索，并返回所有候选的详情列表。

`advanced-search` 第一版不提供 negative 条件。搜索结果在服务内存中保留 10 分钟，
这段时间内把搜索得到的 URL 传给 `get-info-from-url` 最可靠。超过 10 分钟仍会尝试，
但动态 URL 可能已经失效。

stdio 额外提供 `login(profile)`、`logout()` 和 `profile://list` resource。
stdio 启动时不会打开浏览器，必须先调用 `login`。`logout` 只关闭浏览器，不删除
Cookie 或已经保存的登录状态。

专业检索示例：

```json
{
  "title": "无心插柳",
  "author": "袁晓燕",
  "journal": "世界经济文汇",
  "limit": 10,
  "sort_by": "relevance"
}
```

## 元数据回查接口

已知文章题名、作者、年份和来源时，可以让程序自动定位唯一记录并补全 metadata：

```python
with CnkiClient(profile="profile1") as client:
    result = client.lookup_metadata(
        "无心插柳——世界杯“爆冷获胜”的贸易创造",
        authors=["袁晓燕", "翁士汉"],
        year=2024,
        source="世界经济文汇",
        limit=10,
    )
```

CLI 的 `tool info` 使用 `--title`、`--author`、`--year`、`--source`、
`--document-type` 和 `--limit`。`--author` 可重复传入；`--journal` 作为
`--source` 的兼容别名保留。

回查先使用知网专业检索并进行候选评分。详情页读取失败时，会自动尝试知网参考
文献导出数据。无法可靠区分多个候选时会返回候选列表，不会自动猜测。

metadata 的结果比 search 更完整，可包含题名、作者、作者单位、来源、发表年份、
卷期、页码、摘要、关键词、DOI 和知网页面地址。知网页面没有提供的字段会为空。
