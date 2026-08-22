# reporadar

**One command to see the state of every git repository on your machine.**

You have a `projects` folder. It has forty repos in it. Which ones have uncommitted work? Which ones have commits you never pushed? Which one was that experiment from eight months ago?

`reporadar` answers all of that in one command — fast, in color, with zero dependencies.

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

- **✓ / ● / ✗** — clean, has changes, has unresolved conflicts
- **⇡2** — 2 commits not pushed yet · **⇣1** — 1 commit behind upstream
- **⚑1** — 1 stash waiting
- **2y ago** — when this repo last saw a commit

## Install

```bash
pip install reporadar        # once published
# or straight from git:
pip install git+https://github.com/yvichyi/reporadar
```

Requires Python 3.10+ and `git` on your PATH. No other dependencies — pure standard library.

## Usage

```bash
reporadar                    # scan the current directory
reporadar ~/projects ~/work  # scan multiple roots, side by side
```

### Focus on what matters

```bash
reporadar --dirty            # only repos with uncommitted changes
reporadar --ahead            # only repos with unpushed commits
reporadar --stale 90         # only repos untouched for 90+ days
reporadar --sort name        # alphabetical (default: most recent activity)
```

### For scripts and CI

```bash
reporadar --json             # machine-readable output
reporadar --dirty --json     # "do I have uncommitted work?" as an exit-quality check
```

### Odds and ends

```bash
reporadar --depth 6          # search deeper directory trees (default 4)
reporadar --ascii            # pure-ASCII glyphs for legacy consoles
reporadar --no-color         # plain output, e.g. for logs
```

Exit codes: `0` fine · `1` nothing found · `2` bad arguments.

## Why reporadar?

| | reporadar | gita | multi-repo shell scripts |
|---|---|---|---|
| Read-only (never touches your repos) | ✓ | actions can push/pull | depends |
| Dependencies | **zero** | several | — |
| Unpushed / behind / stash at a glance | ✓ | partial | roll your own |
| Works everywhere (Windows/macOS/Linux) | ✓ | ✓ | painful |

reporadar is deliberately **read-only**: it only ever runs `git status`, `git log`, and `git stash list`. It can't lose your work.

## How fast is it?

Repos are scanned in parallel. A folder with 100 repos typically reports in well under a second — the bottleneck is spawning `git`, and reporadar spawns as few processes as possible per repo.

## Development

```bash
git clone https://github.com/yvichyi/reporadar
cd reporadar
python -m unittest discover -s tests -v   # 18 tests, no network needed
```

## License

[MIT](LICENSE)
