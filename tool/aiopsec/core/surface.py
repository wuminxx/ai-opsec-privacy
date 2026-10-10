"""落盘取证面测绘 —— 找 AI 客户端在本机留下的东西。"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

HOME = Path.home()


@dataclass
class Target:
    path: Path
    app: str
    desc: str
    sensitive: bool = False


@dataclass
class SurfaceHit:
    path: str
    app: str
    desc: str
    bytes: int
    files: int
    sensitive: bool
    newest: float = 0.0
    samples: list[str] = field(default_factory=list)

    @property
    def human_bytes(self) -> str:
        b = self.bytes
        for unit, div in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
            if b >= div:
                return f"{b / div:.2f} {unit}"
        return f"{b} B"


def _t(p: str, app: str, desc: str, sensitive: bool = False) -> Target:
    return Target(Path(os.path.expandvars(p)).expanduser(), app, desc, sensitive)


def default_targets() -> list[Target]:
    return [
        # ---- Claude Code ----
        _t("~/.claude/projects", "claude-code", "会话 transcript（明文 JSONL）", True),
        _t("~/.claude/history.jsonl", "claude-code", "输入过的每条 prompt", True),
        _t("~/.claude/memory", "claude-code", "跨会话 memory", True),
        _t("~/.claude/todos", "claude-code", "任务清单", False),
        _t("~/.claude/shell-snapshots", "claude-code", "shell 快照（含 env）", True),
        _t("~/.claude/statsig", "claude-code", "遥测 ID", False),
        _t("~/.claude/plugins", "claude-code", "插件缓存", False),
        # ---- Codex ----
        _t("~/.codex/sessions", "codex", "会话记录", True),
        _t("~/.codex/history.jsonl", "codex", "输入历史", True),
        _t("~/.codex/log", "codex", "日志", True),
        # ---- Cursor ----
        _t("~/.cursor/logs", "cursor", "日志", False),
        _t("~/.cursor/User/History", "cursor", "文件编辑历史", True),
        _t("~/.cursor/User/globalStorage", "cursor", "AI 对话存储", True),
        _t("~/AppData/Roaming/Cursor/User/History", "cursor", "文件编辑历史", True),
        _t("~/AppData/Roaming/Cursor/User/globalStorage", "cursor", "AI 对话存储", True),
        _t("~/Library/Application Support/Cursor/User/History", "cursor", "文件编辑历史", True),
        _t("~/Library/Application Support/Cursor/User/globalStorage", "cursor", "AI 对话存储", True),
        # ---- Continue ----
        _t("~/.continue/sessions", "continue", "会话", True),
        _t("~/.continue", "continue", "配置与会话", True),
        # ---- Aider ----
        _t("~/.aider/analytics.jsonl", "aider", "使用分析", False),
        _t("~/.aider", "aider", "配置", False),
        # ---- VS Code / Copilot ----
        _t("~/AppData/Roaming/Code/User/globalStorage/github.copilot-chat",
           "vscode-copilot", "Copilot 对话存储", True),
        _t("~/.config/Code/User/globalStorage/github.copilot-chat",
           "vscode-copilot", "Copilot 对话存储", True),
        _t("~/Library/Application Support/Code/User/globalStorage/github.copilot-chat",
           "vscode-copilot", "Copilot 对话存储", True),
        # ---- 本地模型 ----
        _t("~/.ollama/models", "ollama", "模型文件", False),
        _t("~/.ollama/logs", "ollama", "日志", True),
        _t("~/.cache/huggingface", "huggingface", "模型缓存", False),
        _t("~/.lmstudio", "lmstudio", "模型与日志", True),
        # ---- 浏览器 ----
        _t("~/.config/google-chrome/Default", "chrome", "浏览器 profile（含 Web 存储）", True),
        _t("~/.config/chromium/Default", "chromium", "浏览器 profile", True),
        _t("~/AppData/Local/Google/Chrome/User Data/Default", "chrome", "浏览器 profile", True),
        _t("~/AppData/Local/Microsoft/Edge/User Data/Default", "edge", "浏览器 profile", True),
        _t("~/Library/Application Support/Google/Chrome/Default", "chrome", "浏览器 profile", True),
        # ---- 其他 agent ----
        _t("~/.opencode", "opencode", "会话与配置", True),
        _t("~/.windsurf", "windsurf", "会话与配置", True),
        _t("~/.config/opencode", "opencode", "配置", False),
    ]


# 会话/历史类文件名特征 —— 命中即高危
SENSITIVE_NAME_HINTS = (
    "history", "session", "transcript", "memory", "conversation",
    "chat", "todos", "projects", "snapshot", "log",
)


def _walk_stats(root: Path, max_files: int = 200_000) -> tuple[int, int, float, list[str]]:
    total = 0
    count = 0
    newest = 0.0
    samples: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # 跳过明显的噪声目录，加速
        dirnames[:] = [d for d in dirnames if d not in
                       (".git", "node_modules", "__pycache__", ".venv", "venv")]
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                st = p.lstat()
            except OSError:
                continue
            total += st.st_size
            count += 1
            if st.st_mtime > newest:
                newest = st.st_mtime
            if len(samples) < 8:
                low = fn.lower()
                if any(h in low for h in SENSITIVE_NAME_HINTS):
                    samples.append(str(p))
            if count >= max_files:
                return total, count, newest, samples
    return total, count, newest, samples


def probe(targets: list[Target] | None = None) -> list[SurfaceHit]:
    targets = targets or default_targets()
    hits: list[SurfaceHit] = []
    seen: set[str] = set()

    for t in targets:
        p = t.path
        if not p.exists():
            continue
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)

        if p.is_file():
            try:
                st = p.stat()
            except OSError:
                continue
            hits.append(SurfaceHit(
                path=str(p), app=t.app, desc=t.desc,
                bytes=st.st_size, files=1,
                sensitive=t.sensitive, newest=st.st_mtime,
                samples=[str(p)] if t.sensitive else [],
            ))
        elif p.is_dir():
            total, count, newest, samples = _walk_stats(p)
            hits.append(SurfaceHit(
                path=str(p), app=t.app, desc=t.desc,
                bytes=total, files=count,
                sensitive=t.sensitive or bool(samples),
                newest=newest, samples=samples,
            ))

    hits.sort(key=lambda h: (-h.sensitive, -h.bytes))
    return hits


def totals(hits: list[SurfaceHit]) -> dict:
    return {
        "paths": len(hits),
        "bytes": sum(h.bytes for h in hits),
        "files": sum(h.files for h in hits),
        "sensitive": sum(1 for h in hits if h.sensitive),
    }
