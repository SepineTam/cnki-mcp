# 安装文档
该项目提供了 MCP，CLI，Python API 等多种使用方式，并附带相关 Skills 和 SubAgents。

该文档中我们以 Claude Code 为例进行安装使用，其他 Agent 安装到对应的目录即可。

## 安装 CNKI-MCP 相关 Plugins 到 Claude Code
先克隆该项目到本地：

```bash
git clone https://github.com/sepinetam/cnki-mcp
cd cnki-mcp
```

安装 Skills

```bash
cp -r plugins/skills/* ~/.claude/skills/
```

安装 SubAgents

```bash
cp -r plugins/agents/* ~/.claude/agents/
```

## 更新 Skills 和 SubAgents

更新前先拉取最新代码，然后逐个比较仓库中的文件和本地已安装文件的哈希值。

```bash
cd cnki-mcp
git pull

# 仓库中文件的哈希值
md5 -q plugins/skills/cnki-search/SKILL.md

# 本地已安装文件的哈希值
md5 -q ~/.claude/skills/cnki-search/SKILL.md
```

两个哈希值一致，说明文件没有变化，无需更新。不一致时，可以考虑通过重新复制完成更新。

```bash
cp -r plugins/skills/* ~/.claude/skills/
cp -r plugins/agents/* ~/.claude/agents/
```

如果已经删除了本地的项目文件夹，重新按照上文的安装步骤操作一遍即可。检查 SubAgents 的更新时使用同样的方法，将路径换成 `plugins/agents/` 和 `~/.claude/agents/` 下对应的文件。
