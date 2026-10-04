# reporadar

**一条命令看清本机所有 Git 仓库，同时给编码 Agent 一层真正只读的 Preflight 传感器。**

> 发布包名：`reporadar-local` · CLI：`reporadar` · Python 包：`reporadar_local`

发布包名和 Python 命名空间刻意避开了生态里已经存在的 RepoRadar 项目；CLI 与协议名称继续保持简短稳定。

## 安装

在正式发布 PyPI 之前，从 GitHub 安装：

```bash
pip install git+https://github.com/yvichyi/reporadar
```

使用 MCP：

```bash
git clone https://github.com/yvichyi/reporadar
cd reporadar
pip install '.[mcp]'
reporadar-mcp
```

需要 Python 3.10+ 与 Git。核心包仍然零运行时依赖。

## 给人看的 CLI

```bash
reporadar
reporadar ~/projects ~/work
reporadar --dirty
reporadar --ahead
reporadar --stale 90
reporadar --json
```

终端表格继续保持快速、跨平台、完全只读。

## Agent 观察协议

`reporadar --agent` 输出 `reporadar.agent/v1`，包括：

- 通用 `ready / review / blocked` 信号；
- 最多 200 条具体变更路径；
- 暂存、未暂存、未跟踪、冲突计数；
- HEAD 标识与 Git status / stash 结构指纹；
- 分支同步、stash、最近提交信息。

旧 `--json` 字段集合保持不变。

## Agent Preflight

```bash
reporadar --preflight read
reporadar --preflight modify
reporadar --preflight commit
reporadar --preflight publish
```

`reporadar.preflight/v1` 会给出 `allow`、`review` 或 `block`，同时解释原因与建议动作。对用户本地改动、冲突、detached HEAD、分支分叉、stash 与发布风险采取保守策略。

完整协议见 [docs/AGENT_PROTOCOL.md](docs/AGENT_PROTOCOL.md)。

## MCP

stdio server 暴露：

- `repository_preflight(path=".", intent="modify")`
- `scan_repositories(paths=None, max_depth=4)`

两个工具都会声明 MCP `read_only_hint=true` 与 `open_world_hint=false`。MCP 只是插头，零依赖 scanner 与版本化协议才是事实源。

## 只读保证

reporadar 只观察仓库状态。它不会运行 push、pull、reset、checkout、stash 修改、commit、add 或任何其他 Git 写操作。

## 开发

```bash
git clone https://github.com/yvichyi/reporadar
cd reporadar
python -m unittest discover -s tests -v
```

CI 覆盖 Python 3.10、3.12、3.14，分别验证纯核心与官方 MCP SDK，并额外构建 wheel 后在源码目录外安装冒烟测试。

## 许可

MIT
