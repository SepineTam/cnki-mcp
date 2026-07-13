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

CLI 和 MCP 的搜索结果保持精简，每条记录只有四项：

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
搜索结果用于浏览和筛选，摘要、关键词、DOI 等详细信息由 metadata 工具返回。

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

检索式作为一个完整参数传入：

```bash
uv run cnki-mcp-cli search "TI='生态' and KY='生态文明'"
uv run cnki-mcp-cli search "TI='生态'" --sort-by date
```

运行下面的命令可以直接查看字段和示例：

```bash
uv run cnki-mcp-cli search --help
```

## MCP 工具

MCP 工具 `cnki_search` 的 `query` 参数接受相同的专业检索式：

```json
{
  "query": "SU='北京' * '奥运' and FT='环境保护'",
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

CLI、Python API 和 MCP 使用相同的字段名称：`title`、`authors`、`year`、
`source`、`document_type` 和 `limit`。CLI 使用 `--author` 表示单个作者，可重复
传入；`--journal` 作为 `--source` 的兼容别名保留。

回查先使用知网专业检索并进行候选评分。详情页读取失败时，会自动尝试知网参考
文献导出数据。无法可靠区分多个候选时会返回候选列表，不会自动猜测。

metadata 的结果比 search 更完整，可包含题名、作者、作者单位、来源、发表年份、
卷期、页码、摘要、关键词、DOI 和知网页面地址。知网页面没有提供的字段会为空。
