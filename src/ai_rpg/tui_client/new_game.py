"""新游戏表单 Screen"""

from datetime import datetime
from typing import List

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Input, Label, RichLog

from ..models import Blueprint
from .server_client import fetch_blueprint_list, login, new_game

FORM_HEADER = """\
[bold cyan]── 开始新游戏 ──────────────────────────────────────[/]

填写用户名后按 [bold]Enter[/]，再输入蓝图编号后按 [bold]Enter[/] 确认，[bold]Escape[/] 返回主菜单。
"""


class NewGameScreen(Screen[None]):
    """新游戏表单 Screen：填写 user_name，从蓝图列表选择游戏后创建。"""

    CSS = """
    NewGameScreen {
        align: center middle;
    }

    #form-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #username-label, #gamename-label {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }

    #username-input, #gamename-input {
        margin: 0 1 1 1;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回主菜单"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._blueprints: List[Blueprint] = []

    def compose(self) -> ComposeResult:
        yield RichLog(id="form-log", highlight=True, markup=True, wrap=True)
        yield Label("用户名 (user_name)：", id="username-label")
        yield Input(
            value=f"player_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            placeholder="用户名",
            id="username-input",
        )
        yield Label("选择游戏（输入编号）：", id="gamename-label")
        yield Input(
            value="1",
            placeholder="输入编号，如 1",
            id="gamename-input",
        )
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(FORM_HEADER)
        self.query_one("#username-input", Input).focus()
        self._load_blueprints()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Input.Submitted, "#username-input")
    def focus_gamename(self, event: Input.Submitted) -> None:
        self.query_one("#gamename-input", Input).focus()

    @on(Input.Submitted, "#gamename-input")
    def submit_form(self, event: Input.Submitted) -> None:
        user_name = self.query_one("#username-input", Input).value.strip()
        raw = self.query_one("#gamename-input", Input).value.strip()
        log = self.query_one(RichLog)

        if not user_name:
            log.write("[red]用户名不能为空[/]")
            self.query_one("#username-input", Input).focus()
            return

        # 有蓝图列表时，用编号索引；否则降级为直接输入游戏名
        if self._blueprints:
            if not raw.isdigit():
                log.write("[red]请输入有效的蓝图编号（数字）[/]")
                return
            idx = int(raw) - 1
            if idx < 0 or idx >= len(self._blueprints):
                log.write(
                    f"[red]编号超出范围，请输入 1–{len(self._blueprints)} 之间的数字[/]"
                )
                return
            game_name = self._blueprints[idx].name
        else:
            if not raw:
                log.write("[red]游戏名不能为空[/]")
                return
            game_name = raw

        self._start_new_game(user_name, game_name)

    @work
    async def _load_blueprints(self) -> None:
        log = self.query_one(RichLog)
        logger.info("_load_blueprints: 正在获取蓝图列表...")
        try:
            resp = await fetch_blueprint_list()
            self._blueprints = resp.blueprints
            if self._blueprints:
                log.write(
                    "[bold cyan]── 可用游戏蓝图 ──────────────────────────────[/]"
                )
                for i, bp in enumerate(self._blueprints, start=1):
                    preview = bp.campaign_setting[:40].replace("\n", " ")
                    log.write(
                        f"  [bold]{i}.[/] [green]{bp.name}[/]  [dim]{preview}…[/]"
                    )
                log.write("")
            else:
                log.write("[yellow]⚠ 服务器暂无可用蓝图，请直接输入游戏名[/]")
            logger.info(
                f"_load_blueprints: 获取成功，共 {len(self._blueprints)} 个蓝图"
            )
        except Exception as e:
            logger.error(f"_load_blueprints: 获取失败 error={e}")
            log.write(f"[yellow]⚠ 蓝图列表获取失败（{e}），请直接输入游戏名[/]")

    @work
    async def _start_new_game(self, user_name: str, game_name: str) -> None:
        log = self.query_one(RichLog)
        log.write(f"[dim]正在登录，user_name={user_name} ...[/]")
        logger.info(
            f"_start_new_game: 开始登录 user_name={user_name} game_name={game_name}"
        )
        try:
            login_msg = await login(user_name, game_name)
            log.write(f"[green]✅ 登录成功：{login_msg}[/]")
            logger.info(
                f"_start_new_game: 登录成功 user_name={user_name} msg={login_msg}"
            )
        except Exception as e:
            logger.error(f"_start_new_game: 登录失败 user_name={user_name} error={e}")
            log.write(f"[bold red]❌ 登录失败: {e}[/]")
            return

        log.write(f"[dim]正在创建游戏，game_name={game_name} ...[/]")
        logger.info(f"_start_new_game: 开始创建游戏 game_name={game_name}")
        try:
            resp = await new_game(user_name, game_name)
            log.write(
                f"[bold green]✅ 游戏已创建！user_name={user_name}，game_name={game_name}[/]"
            )
            logger.info(
                f"_start_new_game: 游戏创建成功 user_name={user_name} game_name={game_name} blueprint={resp.blueprint!r} → 进入 HomeScreen"
            )
            from .app import GameClient
            from .home import HomeScreen

            app: GameClient = self.app  # type: ignore[assignment]
            app.session_user_name = user_name
            app.session_game_name = game_name
            app.session_blueprint = resp.blueprint
            app.switch_screen(HomeScreen(user_name=user_name, game_name=game_name))
        except Exception as e:
            logger.error(
                f"_start_new_game: 创建游戏失败 game_name={game_name} error={e}"
            )
            log.write(f"[bold red]❌ 创建游戏失败: {e}[/]")
