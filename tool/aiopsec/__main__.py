"""aiopsec —— AI 使用 OPSEC 工具

入口：python -m aiopsec <command>
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .commands import (audit_cmd, check_cmd, env_cmd, harden_cmd,
                       hook_cmd, redact_cmd, scan_cmd, shred_cmd)

COMMANDS = {
    "scan": scan_cmd,
    "check": check_cmd,
    "redact": redact_cmd,
    "shred": shred_cmd,
    "env": env_cmd,
    "harden": harden_cmd,
    "hook": hook_cmd,
    "audit": audit_cmd,
}

EPILOG = """\
示例:
  aiopsec audit                      全量体检（先跑这个）
  aiopsec scan                       测绘落盘取证面
  aiopsec check -f app.log           检查文件里的身份泄漏
  aiopsec redact < app.log > clean.log
  aiopsec shred --force              清理会话痕迹
  aiopsec env                        检查时区/语言/IP 一致性
  aiopsec harden --apply             关闭遥测 + 加固配置
  aiopsec hook --install --apply     装 Claude Code 拦截 hook

退出码:
  0 = 通过    1 = 发现问题    2 = 用法错误
"""


def build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aiopsec",
        description="AI 使用 OPSEC 工具 —— 落盘测绘 / 泄露检查 / 脱敏 / 清理 / 加固",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-V", "--version", action="version",
                   version=f"aiopsec {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>")
    for name, mod in COMMANDS.items():
        mod.add_parser(sub)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    fn = getattr(args, "func", None)
    if fn is None:
        parser.print_help()
        return 2
    try:
        return fn(args) or 0
    except KeyboardInterrupt:
        print("\n中断", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
