"""启动 Screen：简单的正文区 + 输入区，支持斜杠命令。"""

import json
from typing import Dict, List, Tuple

from loguru import logger
from rich.console import RenderableType
from rich.syntax import Syntax
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static

from .config import server_config
from .server_client import fetch_server_info

INTRO_TEXT = """\
[bold cyan]测试TUI用客户端 v0.0.1[/]
[dim]输入 [bold]/[/] 查看可用命令。[/]
"""

# 命令定义：(完整命令, 简写, 说明)，顺序即 /help 展示顺序
COMMAND_DEFS: List[Tuple[str, str, str]] = [
    ("help", "h", "显示本帮助"),
    ("server", "s", "获取服务器信息"),
    ("new", "n", "开始新游戏"),
    ("clear", "c", "清空正文区"),
    ("quit", "q", "退出游戏"),
]

# 命令名（完整或简写）→ 完整命令名
COMMAND_ALIASES: Dict[str, str] = {
    alias: full
    for full, short, _ in COMMAND_DEFS
    for alias in (full, short)
}


def _build_help_text() -> str:
    lines = ["[bold yellow]可用命令：[/]", ""]
    for full, short, desc in COMMAND_DEFS:
        lines.append(f"  [bold green]/{full}[/] [dim](/{short})[/]  {desc}")
    lines.append("")
    lines.append("[dim]直接输入 [bold]/[/] 亦可显示本帮助。[/]")
    return "\n".join(lines)


HELP_TEXT = _build_help_text()


class LaunchScreen(Screen[None]):
    """启动 Screen：正文区累加展示信息，输入区接收斜杠命令。"""

    CSS = """
    LaunchScreen {
        align: center middle;
    }

    #body {
        height: 1fr;
        padding: 0 1;
    }

    #input-row {
        height: 3;
        dock: bottom;
    }

    #prompt {
        width: 3;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #command-input {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield RichLog(id="body", highlight=True, markup=True, wrap=True)
        with Horizontal(id="input-row"):
            yield Static("> ", id="prompt")
            yield Input(
                placeholder="输入 / 查看帮助，或输入 /command",
                id="command-input",
            )

    def on_mount(self) -> None:
        self._write(INTRO_TEXT)
        self.query_one("#command-input", Input).focus()

    def _write(self, text: RenderableType) -> None:
        """把信息追加写入正文区。"""
        self.query_one("#body", RichLog).write(text)

    @on(Input.Submitted, "#command-input")
    def _on_submit(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()

        # 空输入或单独输入 '/'：等同于帮助
        if not raw or raw == "/":
            self._write("")
            self._write(HELP_TEXT)
            return

        if not raw.startswith("/"):
            self._write("")
            self._write(f"[dim]未知输入：{raw}，输入 [bold]/[/] 查看可用命令。[/]")
            return

        parts = raw[1:].strip().split(maxsplit=1)
        name = parts[0].lower() if parts else ""
        args = parts[1].strip() if len(parts) > 1 else ""

        canonical = COMMAND_ALIASES.get(name)
        if canonical is None:
            self._write("")
            self._write(f"[red]未知命令：/{name}，输入 [bold]/[/] 查看可用命令。[/]")
            return

        handler = getattr(self, f"_cmd_{canonical}", None)
        if handler is not None:
            # 空行分隔每条命令产生的输出
            self._write("")
            handler(args)

    # ── 命令处理 ──

    def _cmd_help(self, args: str) -> None:
        self._write(HELP_TEXT)

    def _cmd_server(self, args: str) -> None:
        self._fetch_server_info()

    def _cmd_new(self, args: str) -> None:
        from .new_game import NewGameScreen

        self.app.push_screen(NewGameScreen())

    def _cmd_clear(self, args: str) -> None:
        self.query_one("#body", RichLog).clear()
        self._write(INTRO_TEXT)

    def _cmd_quit(self, args: str) -> None:
        self.app.exit()

    # ── 后台任务 ──

    @work
    async def _fetch_server_info(self) -> None:
        self._write(f"[dim]正在获取服务器信息 {server_config.base_url} ...[/]")
        logger.info(f"fetch_server_info: 请求 url={server_config.base_url}")
        try:
            info = await fetch_server_info()
            logger.info(f"fetch_server_info: 成功 url={server_config.base_url}")
            self._write("[bold green]✅ 服务器信息：[/]")
            info_json = json.dumps(info, indent=2, ensure_ascii=False)
            self._write(Syntax(info_json, "json", theme="ansi_dark", word_wrap=True))
        except Exception as e:
            logger.error(
                f"fetch_server_info: 失败 url={server_config.base_url} error={e}"
            )
            self._write(f"[bold red]❌ 获取失败: {e}[/]")
            self._write("[dim]请确认游戏服务器已启动。[/]")
