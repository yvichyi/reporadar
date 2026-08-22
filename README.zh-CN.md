# reporadar

**一条命令，看清你电脑上所有 Git 仓库的状态。**

你有一个 `projects` 文件夹，里面躺着几十个仓库。哪些有没提交的改动？哪些提交了却忘了 push？哪个是八个月前的试验品？

`reporadar` 一条命令全部告诉你——快速、彩色、零依赖。

```text
REPO           BRANCH      STATUS       SYNC         LAST COMMIT  STASH
-------------  ----------  -----------  -----------  -----------  -----
gamma          main        ✓ clean      ⇡2           just now     —
legacy-tool    (detached)  ✓ clean      —            just now     —
web-app        main        ✓ clean      ⇣1           just now     ⚑1
beta           main        ● 3 changes  no upstream  just now     —
alpha          main        ✓ clean      ✓ synced     just now     —
data-pipeline  main        ✓ clean      no upstream  2y ago       —

6 repos · 1 dirty · 1 unpushed · 1 stashed
```

- **✓ / ● / ✗** — 干净 / 有改动 / 有未解决的冲突
- **⇡2** — 有 2 个提交还没 push · **⇣1** — 落后远程 1 个提交
- **⚑1** — 有 1 个 stash 挂着
- **2y ago** — 这个仓库最后一次提交是什么时候

## 安装

```bash
pip install reporadar        # 发布后
# 或直接从 GitHub 安装：
pip install git+https://github.com/yvichyi/reporadar
```

需要 Python 3.10+ 和 PATH 里的 `git`。除此之外**零依赖**——纯标准库实现。

## 使用

```bash
reporadar                    # 扫描当前目录
reporadar ~/projects ~/work  # 同时扫描多个目录
```

### 只看要紧的

```bash
reporadar --dirty            # 只看有未提交改动的仓库
reporadar --ahead            # 只看有未 push 提交的仓库
reporadar --stale 90         # 只看 90 天没动过的仓库
reporadar --sort name        # 按名称排序（默认按最近活跃）
```

### 给脚本和 CI 用

```bash
reporadar --json             # 机器可读输出
reporadar --dirty --json     # "有没有没提交的工作？"一查便知
```

### 其他

```bash
reporadar --depth 6          # 搜得更深（默认 4 层）
reporadar --ascii            # 纯 ASCII 符号，兼容老终端
reporadar --no-color         # 无色输出，适合写日志
```

退出码：`0` 正常 · `1` 没找到仓库 · `2` 参数错误。

## 为什么选 reporadar？

| | reporadar | gita | 手写脚本 |
|---|---|---|---|
| 只读（绝不碰你的仓库） | ✓ | 可执行 push/pull | 看手气 |
| 依赖 | **零** | 若干 | — |
| 未 push / 落后 / stash 一屏尽览 | ✓ | 部分 | 自己造轮子 |
| 跨平台（Windows/macOS/Linux） | ✓ | ✓ | 写到吐血 |

reporadar 刻意保持**只读**：它只会运行 `git status`、`git log`、`git stash list`，绝不会弄丢你的工作。

## 性能

仓库并行扫描。100 个仓库的目录通常一秒内出结果——瓶颈只在启动 `git` 进程，而 reporadar 已把每个仓库的 git 调用压到最少。

## 开发

```bash
git clone https://github.com/yvichyi/reporadar
cd reporadar
python -m unittest discover -s tests -v   # 18 个测试，无需联网
```

## 许可

[MIT](LICENSE)
