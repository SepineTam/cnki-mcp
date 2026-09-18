---
name: cnki-search
description: 使用 cnki-mcp 检索知网文献、按篇名和作者等字段组合查询、获取摘要及题录元数据、列出期刊某一期目录。适用于知网文献检索与元数据整理；Chrome 或 computer use 网页操作使用 explore-cnki-view。
---

# 知网文献检索

将研究问题或题录条件转为可复查的知网检索，交付文献清单及按需取得的元数据。优先使用已连接的 cnki-mcp MCP 工具。需要原始专业检索式或没有可用 MCP 连接时，使用已安装的 CLI / Python API。

## 选择入口

| 需求 | 入口 |
|---|---|
| 普通搜索词、先了解有哪些文献 | `easy-search` |
| 篇名、作者、主题、关键词、期刊等条件同时成立 | `advanced-search` |
| 从搜索结果获取详情 | `get-info-from-url` |
| 已知篇名及作者、年份等题录，直接取详情 | `get-info-by-detail` |
| 查期刊 ISSN，再取某一期目录 | `search-issn` → `list-journal` |
| 作者择一、排除、第一作者等复杂专业表达式 | CLI `tool search --advanced` 或 Python `client.search` |
| 指定 Chrome / computer use，或需要核对网页 | 读取同插件的 `explore-cnki-view` skill |

这些是服务端注册名，含连字符。宿主可能添加工具前缀，以当前工具列表及 schema 为准，不凭记忆猜工具名。

## 连接与登录

- HTTP / SSE 提供六个业务工具，服务启动时处理登录，没有 `login` / `logout` 工具。重新认证需在服务所在机器进行，不能拿本机 CLI 登录代替远程服务器登录。
- stdio 额外提供 `login(profile?)`、`logout()` 和 `profile://list` 资源。首次检索前用 `login` 启动浏览器；profile 不明确时通过该资源发现已有名称，不读取个人配置文件。
- 本机首次初始化使用 `cnki-mcp init -p <profile>`，会设置默认 profile；已有 profile 使用 `cnki-mcp login -p <profile>`。登录、机构认证和验证码由用户完成。登录态会过期，不承诺永久有效。
- MCP、CLI 和手动 Chrome 的会话不保证相同。避免多个进程同时占用同一个持久化 profile。

## 执行检索

先根据用户条件做小规模检索。普通主题用 `easy-search`；有明确字段限制时，先读 [字段、参数与专业语法](references/search-syntax.md)，构造 `advanced-search` 参数。

结构化参数只填字段值，例如 `title="平台经济"`。不要把 `TI='平台经济'` 塞进 `title`。各字段自动用 `and` 连接；需要 `or` / `not` 或 `FI` / `RP` 等未暴露字段时走原始表达式入口。年份明确传起止两端，避免单边年份被解释为单年。

核对结果的篇名、作者、年份和来源。结果太少时有依据地调整条件并记录变化，不静默去掉用户要求的年份、期刊或来源类别。空结果只说明当前查询未返回文献。

MCP 搜索返回 `title`、`authors`、`journal`、`date`、`url`。要摘要或 DOI 时，将实际返回的 URL 交给 `get-info-from-url`，尽量在检索后十分钟内读取。旧 URL 仍会尝试，但可能失效。CLI 搜索仅返回前四个字段，没有 URL，可用题录定位详情。

只对任务需要的文献取详情。`get-info-by-detail` 会搜索并逐篇读取，返回列表，不保证唯一匹配。失败条目带 `success: false` 和 `error`，不等于元数据字段为空。CLI `info --title` / Python `lookup_metadata` 则返回含 `is_unique`、`candidates`、`article` 的匹配对象，不能混用解释。

具体调用顺序见 [完整调用示例](references/examples.md)。

## 输出与异常

结果至少包含标题、作者、来源、日期；有真实 URL 时附链接。摘要来自详情元数据，缺失字段保留为空或写“未提供”，不将摘要概述当作全文阅读结论。保留检索词或表达式、过滤条件、排序及实际返回条数，让结果可复查。前十篇不等于全部相关文献。

浏览器检索可能耗时较长，同一请求执行中不要重复提交。登录失效或出现实际可见的安全验证阻断时暂停，由用户处理；限速或配额按错误提示等待，不切换账号规避。解析失败时记录实际错误与步骤，必要时交给网页 skill 核对。CLI 与 MCP 共用核心实现，换入口不保证解决网页变化，不反复重跑同一失败查询。

## 边界

- cnki-mcp 只检索和获取元数据，不提供或实现全文下载。`FT` 是检索范围，`download_url` 是元数据字段，都不代表下载能力或授权。
- 用户希望通过网页下载时，交给 `cnki-in-chrome-use` Agent / `explore-cnki-view` skill，遵守该流程下载前询问的要求。本 skill 不触发下载。
- 查资料不构成使用用户邮箱、提交文献传递或注册表单的授权。

## 使用许可与版权声明

GNU 3.0 License

补充条款：该项目（https://github.com/sepinetam/cnki-mcp）及其所有附属内容均为个人研究与学习的项目，不得用于商业用途或任何非法用途，包括但不限于以盈利为目的分发该项目、将该项目集成于任何产品或项目以获取收益、批量检索中国知网或形同构成攻击行为以及
