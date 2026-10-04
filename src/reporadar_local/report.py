"""Render a colored one-screen report of all repositories."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from .model import RepoStatus


# ---------------------------------------------------------------- colors ---

class Palette:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


class Painter:
    """Applies (or drops, when disabled) ANSI styling."""

    def __init__(self, enabled: bool):
        self.on = enabled

    def c(self, code: str, text: str) -> str:
        return f"{code}{text}{Palette.RESET}" if self.on else text


def enable_windows_vt() -> None:
    """Turn on VT processing so ANSI colors work in classic Windows consoles."""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING


# ----------------------------------------------------------------- time ----

def relative_time(ts: float | None, now: float | None = None) -> str:
    if ts is None:
        return "no commits"
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    secs = max(0, now - ts)
    if secs < 60:
        return "just now"
    mins = int(secs // 60)
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    return f"{days // 365}y ago"


# ---------------------------------------------------------------- table ----

class Symbols:
    """Unicode glyphs, with an ASCII fallback set for legacy consoles."""

    def __init__(self, ascii_only: bool):
        if ascii_only:
            self.clean, self.dirty, self.conflict = "ok", "!!", "XX"
            self.up, self.down, self.stash, self.none = "^", "v", "#", "-"
        else:
            self.clean, self.dirty, self.conflict = "✓", "●", "✗"
            self.up, self.down, self.stash, self.none = "⇡", "⇣", "⚑", "—"


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def render(repos: list[RepoStatus], color: bool = True, ascii_only: bool = False) -> str:
    """Build the full report as a string (table + summary footer)."""
    p = Painter(color)
    s = Symbols(ascii_only)
    now = datetime.now(timezone.utc).timestamp()

    rows: list[tuple[RepoStatus, list[str], list[str]]] = []
    for r in repos:
        # (repo, plain cells, colored cells) — plain drives column widths.
        if r.error:
            status_plain = f"{s.conflict} error"
            status = p.c(Palette.RED, status_plain)
        elif r.has_conflicts:
            status_plain = f"{s.conflict} {r.conflicted} conflict" + ("s" if r.conflicted > 1 else "")
            status = p.c(Palette.RED, status_plain)
        elif r.is_dirty:
            status_plain = f"{s.dirty} {r.changed} change" + ("s" if r.changed > 1 else "")
            status = p.c(Palette.YELLOW, status_plain)
        else:
            status_plain = f"{s.clean} clean"
            status = p.c(Palette.GREEN, status_plain)

        if r.error:
            sync_plain, sync = "", ""
        elif r.branch == "(detached)":
            sync_plain = s.none
            sync = p.c(Palette.DIM, sync_plain)
        elif not r.has_upstream:
            sync_plain = "no upstream"
            sync = p.c(Palette.DIM, sync_plain)
        else:
            parts, sync_plain = [], ""
            if r.ahead:
                parts.append(f"{s.up}{r.ahead}")
                sync_plain += f"{s.up}{r.ahead} "
            if r.behind:
                parts.append(f"{s.down}{r.behind}")
                sync_plain += f"{s.down}{r.behind} "
            if parts:
                colored = [p.c(Palette.RED, t) if t.startswith(s.up)
                           else p.c(Palette.YELLOW, t) for t in parts]
                sync = " ".join(colored)
                sync_plain = sync_plain.strip()
            else:
                sync_plain = f"{s.clean} synced"
                sync = p.c(Palette.GREEN, sync_plain)

        age = relative_time(r.last_commit_ts, now)
        if r.last_commit_ts is None:
            age_c = p.c(Palette.DIM, age)
        elif now - r.last_commit_ts > 60 * 86400:
            age_c = p.c(Palette.RED, age)
        elif now - r.last_commit_ts > 14 * 86400:
            age_c = p.c(Palette.YELLOW, age)
        else:
            age_c = p.c(Palette.GREEN, age)

        stash = str(r.stashes) if r.stashes else s.none
        stash_c = p.c(Palette.MAGENTA, f"{s.stash}{r.stashes}") if r.stashes else p.c(Palette.DIM, stash)

        plain = [r.name, r.branch or "-", status_plain, sync_plain, age, stash]
        fancy = [
            p.c(Palette.BOLD, r.name) if r.is_dirty or r.is_unpushed or r.has_conflicts else r.name,
            p.c(Palette.CYAN, r.branch or "-"),
            status, sync, age_c, stash_c,
        ]
        rows.append((r, plain, fancy))

    headers = ["REPO", "BRANCH", "STATUS", "SYNC", "LAST COMMIT", "STASH"]
    widths = [len(h) for h in headers]
    for _r, plain, _f in rows:
        for i, cell in enumerate(plain):
            widths[i] = min(40, max(widths[i], len(cell)))

    out: list[str] = []
    header = "  ".join(
        p.c(Palette.BOLD + Palette.BLUE, h) + " " * (widths[i] - len(h))
        for i, h in enumerate(headers)
    )
    out.append(header)
    out.append(p.c(Palette.DIM, "  ".join("-" * w for w in widths)))

    for _r, plain, fancy in rows:
        # Pad each colored cell using its plain twin's length.
        cells = []
        for i in range(len(headers)):
            pad = widths[i] - len(plain[i])
            cells.append(_truncate_fancy(fancy[i], plain[i], widths[i]) + " " * max(0, pad))
        out.append("  ".join(cells).rstrip())

    out.append("")

    total = len(repos)
    dirty = sum(1 for r in repos if r.is_dirty)
    unpushed = sum(1 for r in repos if r.is_unpushed)
    conflicts = sum(1 for r in repos if r.has_conflicts)
    stashes = sum(r.stashes for r in repos)
    errors = sum(1 for r in repos if r.error)

    bits = [
        f"{p.c(Palette.BOLD, str(total))} repo" + ("" if total == 1 else "s"),
        f"{p.c(Palette.YELLOW, str(dirty))} dirty",
        f"{p.c(Palette.RED, str(unpushed))} unpushed",
    ]
    if conflicts:
        bits.append(p.c(Palette.RED, f"{conflicts} in conflict"))
    if stashes:
        bits.append(p.c(Palette.MAGENTA, f"{stashes} stashed"))
    if errors:
        bits.append(p.c(Palette.RED, f"{errors} errored"))
    out.append(" · ".join(bits))
    return "\n".join(out)


def _truncate_fancy(fancy: str, plain: str, width: int) -> str:
    """Truncate a possibly-colored cell based on its plain length.

    Oversized cells lose their color rather than being mismeasured —
    correctness of the grid beats styling in the rare wide case.
    """
    return fancy if len(plain) <= width else _truncate(plain, width)
