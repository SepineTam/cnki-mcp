# cnki-mcp
An MCP server for reach CNKI. 

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

## 文档

- [Python API 与专业检索式](docs/api.md)
