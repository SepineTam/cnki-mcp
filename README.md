# cnki-mcp
An MCP server for reach CNKI. 

> 免责声明：该项目仅为个人学习项目，且仅供学习参考。 
> 该项目不隶属任何公司、机构，与中国知网（下简称为知网或CNKI）无任何所属关系。 
> 该项目不应用于非法手段，包括但不限于：批量访问知网进行搜索，以非正规途径获取知网论文，利用该项目进行违法违规的行为。 
> 如有上述行为，本项目不构成任何因果利害关系，由使用者自行负责。最终解释权归本项目所有。 

## 首次初始化

首次使用时运行：

```bash
uv run cnki-mcp init
```

命令会询问 Profile 名称，直接回车使用 `default`。也可以直接指定名称：

```bash
uv run cnki-mcp init --profile school
```

请在打开的浏览器中完成学校或机构认证。初始化成功后，该 Profile 会成为默认
Profile，后续启动和检索无需重复指定。

## 推荐启动方式

推荐使用 HTTP。下面两条命令效果相同，默认监听 `127.0.0.1:7788`：

```bash
uv run cnki-mcp
uv run cnki-mcp serve --transport http --host 127.0.0.1 --port 7788
```

服务启动时会打开一个持久浏览器，并在服务进程退出时关闭。项目只提供知网检索和
文章信息读取，不提供全文下载。

按 ISSN 获取某一期的全部文章 metadata：

```bash
uv run cnki-mcp tool journal --issn 1002-9621 --year 2026 --vol 1
```

这里的 `--vol` 表示知网页面上的期号。返回结果会把真正的卷号 `volume` 和期号
`issue` 分开提供。尚未发行的年份或期号会返回 `IssueNotAvailable`。

通过期刊名称搜索 ISSN：

```bash
uv run cnki-mcp tool issn --journal "世界经济"
```

搜索会忽略期刊名中的空格和标点，并返回知网搜索到的全部候选期刊。期刊目录来自
知网期刊导航页。工具每次都会通过 ISSN 重新定位期刊并获取当次有效的页面地址，
不会保存其中会失效的 `p` 参数。

## 通过 Python 使用
该项目提供了 Python API 供学习参考：

```python
# pip install cnki-mcp

from cnki_mcp import CnkiClient

with CnkiClient(profile="profile1") as client:
    results = client.search(
        "TI='生态' and KY='生态文明'",
        sort_by="date",
    )
```

## 文档

- [Python API 与专业检索式](docs/api.md)
