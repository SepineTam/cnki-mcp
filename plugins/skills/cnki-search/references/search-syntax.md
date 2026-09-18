# 检索字段、参数与专业语法

字段与参数按当前 cnki-mcp 实现整理。表达式由知网页面解释，不同资源库的字段可用性、匹配规则需结合当前页面帮助和结果核对。

## 字段怎么选

| 代码 | 名称 | 如何使用 | `advanced-search` 参数 |
|---|---|---|---|
| `TI` | 篇名 | 找标题含某词的文章，或用已知篇名定位，仍须核对完整标题 | `title` |
| `AU` | 作者 | 查任意署名作者；同名者结合单位、篇名、来源核对 | `author` |
| `SU` | 主题 | 围绕研究概念查文献，范围由知网主题检索规则确定 | `subject` |
| `KY` | 关键词 | 限定文献标引的关键词 | `keywords` |
| `AB` | 摘要 | 要求概念出现在摘要字段 | `abstract` |
| `AF` | 作者单位 | 按机构查询，命中不代表每位作者都属于该机构 | `institution` |
| `FU` | 基金 | 按基金名称或页面支持的基金信息检索 | `fund` |
| `LY` | 文献来源 | 例如某本期刊；不同文献类型需核对来源含义 | `journal` |
| `DOI` | DOI | 用已知 DOI 定位，再核对篇名与作者 | `doi` |
| `TKA` | 篇关摘 | 在篇名、关键词、摘要范围检索 | 无，走原始表达式 |
| `FT` | 全文 | 在全文字段查词，不返回或下载全文 | 无，走原始表达式 |
| `FI` | 第一作者 | 用户明确要求第一署名作者时使用 | 无，不能用 `author` 代替 |
| `RP` | 通讯作者 | 用户明确要求通讯作者时使用 | 无，不能用 `author` 代替 |
| `CO` | 小标题 | 查正文中的小标题 | 无，走原始表达式 |
| `RF` | 参考文献 | 查参考文献字段，不等于完整引文网络 | 无，走原始表达式 |
| `CLC` | 分类号 | 按中图分类号检索 | 无，走原始表达式 |
| `CF` | 被引频次 | 数值条件先核对页面帮助，不猜比较运算符 | 无；排序可用 `sort_by="citation"` |

上表九个 MCP 文本参数均为字符串。`SU` 和 `TKA` 不应未经核对视为完全相同。`TI='某词'` 不能直接宣称是完整标题精确相等；程序生成等号子句，最终匹配规则由知网决定。

## MCP 六个业务工具

以下是服务端名称，调用使用宿主当前实际暴露的工具和 schema。

### `easy-search`

必填 `keywords: str`，可选 `limit: int = 10`、`sort_by: str | null`。不接受年份、来源类别等高级参数，需要这些条件时用 `advanced-search`。

### `advanced-search`

下面九个文本参数至少提供一个非空值：

```text
title, author, journal, keywords, subject, abstract, institution, fund, doi
```

分别映射到 `TI AU LY KY SU AB AF FU DOI`，各子句以 `and` 连接。其他参数：

```text
year_from: int | null
year_to: int | null
document_type: str | null
source_types: list[str] | null
sort_by: str | null
limit: int = 10
```

`{"title":"平台经济","author":"张三"}` 生成 `TI='平台经济' and AU='张三'`。`{"author":"张三 or 李四"}` 只是一个作者字段值，不能表达作者择一。没有 `expression`、`query` 或 `TI` 参数，也不能仅靠年份或类别发起调用。

### `get-info-from-url`

必填 `url: str`，来自真实搜索结果。结果缓存十分钟，过期仍尝试读取；失败时重新检索取得新 URL，不拼接加密详情地址。

返回文章对象，含 `article_id`、`title`、`authors`、`institution`、`abstract`、`keywords`、`year`、`source`、`volume`、`issue`、`pages`、`doi`、`url`、`download_url`。字段可能为空，`download_url` 不表示支持下载。

### `get-info-by-detail`

必填 `title: str`。可选 `authors: list[str]`、`year: int`，以及 `year_from`、`year_to`、`journal`、`keywords`、`subject`、`abstract`、`institution`、`fund`、`doi`、`document_type`、`source_types`、`sort_by`、`limit`，类型同上，默认 `limit=10`。

这里是复数 `authors`，多位作者以 `and` 联合限定；`advanced-search` 是单数 `author`。缺省的年份端点从 `year` 取得，故单年只用 `year`，范围同时用 `year_from` 与 `year_to`，避免混合。

返回文章对象列表，可能多篇、零篇或夹杂 `success: false` / `error` 的失败条目。逐一核对，不能默认首条就是目标。该工具不返回 `is_unique`。

### `search-issn`

必填 `journal: str`，按期刊名称查询，返回“期刊名称 → ISSN”的字典，如 `{"经济研究":"0577-9154"}`。可能含多个候选，先匹配目标期刊名，再取对应 ISSN；不要当作带 `name` / `issn` 两个字段的对象，也不要编造 ISSN。

### `list-journal`

必填 `issn: str`、`year: int`、`vol: int | str`。`vol` 是知网页面上的期号，如 `3` / `"03"`，不是书目卷号。返回 `name`、`issn`、`year`、`volume`、`issue`、`count`、`articles`，文章列表已含该期解析得到的完整元数据。

## 原始专业表达式

复杂布尔组合或未暴露字段走 CLI `cnki-mcp tool search --advanced "表达式"`，或 Python `client.search("表达式")`。

子句如 `TI='平台经济'`，字段间用 `and`、`or`、`not`，以括号明确分组。同字段词项可用 `*`（与）、`+`（或）、`-`（排除）。`%` 用于模糊匹配，具体分词与匹配以知网当前帮助为准。使用英文半角符号与成对引号。

```text
TI='平台经济' and (AU='张三' or AU='李四')
TI='生态' and KY='生态文明' and (AU % '陈' + '王')
SU='北京' * '奥运' and FT='环境保护'
SU=('经济发展' + '可持续发展') * '转变' - '泡沫'
```

这些是语法例子，不代表已检索到文献。模糊作者匹配要核对实际人名。词语含引号或运算符时先查当前帮助，不猜转义规则；结构化字段同时含单双引号会被程序拒绝。

## 年份、来源与排序

| 参数 | 用法 |
|---|---|
| `year_from` / `year_to` | 同时传起止年份，含两端；当前实现仅传一端会补成同年，不能表达“某年以后” |
| `document_type` | 常用 `学术期刊`、`学位论文`、`会议`、`报纸`，实际分类需核对 |
| `source_types` | 列表，支持 `CSSCI`、`SCI`、`EI`、`CSCD`、`AMI`、`WJCI`、`北大核心`；多选不能未经核对宣称是交集 |
| `sort_by` | `relevance` 相关度、`date` 发表时间、`citation` 被引、`comprehensive` 综合；未传依赖页面默认 |
| `limit` | 返回条数上限，默认 10，不是总命中数 |

CLI 普通检索与 `--advanced` 都可叠加 `--limit`、`--sort-by`、`--year-from`、`--year-to`、`--journal`、`--author`、`--institution`、`--document-type`；类别用可重复的 `--source-type CSSCI --source-type 北大核心`。

CLI 搜索的 `--author` 是单值，CLI `info --author` 可重复。MCP `easy-search` 不接受这些 CLI 过滤条件，入口之间不能照搬参数。
