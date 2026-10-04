# reporadar

**一条命令看清本机所有 Git 仓库，也给编码 Agent 一层真正只读的环境传感器。**

```text
REPO           BRANCH      STATUS       SYNC         LAST COMMIT  STASH
-------------  ----------  -----------  -----------  -----------  -----
web-app        main        ● 3 changes  ⇡2           4m ago       ⚑1
alpha          main        ✓ clean      ✓ synced     2h ago       —
legacy-tool    (detached)  ✓ clean      —            8mo ago      —
```

## 安装

```bash
pip install reporadar

# 可选 MCP v2 适配层
pip install "reporadar[mcp]"
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

表格输出继续保持快速、跨平台、完全只读。

## Agent 观察协议

`reporadar --agent` 输出版本化的 `reporadar.agent/v1`，现在包含：

- 通用 `ready / review / blocked` 信号；
- 最多 200 条具体变更路径；
- 暂存、未暂存、未跟踪、冲突计数；
- HEAD 标识与 Git status / stash 结构指纹；
- 分支同步、stash、最近提交信息。

旧 `--json` 字段集合保持不变。

## Agent Preflight 策略

“观察事实”和“是否适合行动”被刻意分开。告诉 reporadar Agent 准备做什么：

```bash
reporadar --preflight read
reporadar --preflight modify
reporadar --preflight commit
reporadar --preflight publish
```

它会输出 `reporadar.preflight/v1`，给出 `allow`、`review` 或 `block`，同时说明原因与建议动作。对用户本地改动、冲突、detached HEAD、分支分叉、stash 与发布风险采取保守策略。

完整协议与兼容性保证见 [docs/AGENT_PROTOCOL.md](docs/AGENT_PROTOCOL.md)。

## MCP

```bash
pip install "reporadar[mcp]"
reporadar-mcp
```

stdio server 暴露两个工具：

- `repository_preflight(path=".", intent="modify")`：检查单仓库，并按意图执行安全策略。
- `scan_repositories(paths=None, max_depth=4)`：用 `agent/v1` 观察一个或多个目录树。

两个工具都会向 MCP 客户端声明只读、封闭世界。MCP 只是插头，零依赖 scanner 与版本化协议才是事实源。

## 为什么要做这个

编码 Agent 不应该从漂亮表格里猜仓库是否安全，也不应该默认工作区是干净的。reporadar 提供的是 Agent 动手前可重复、可解释的环境感知层。

它不会执行 push、pull、reset、checkout、stash 修改或任何其他写操作。

## 开发

```bash
git clone https://github.com/yvichyi/reporadar
cd reporadar
python -m unittest discover -s tests -v
```

CI 同时覆盖最低支持版本与较新的 Python，并分别验证纯核心与官方 MCP SDK。

## 许可

MIT
