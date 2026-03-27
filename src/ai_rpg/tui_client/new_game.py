"""新游戏表单 Screen"""

import time

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Input, Label, RichLog

from .server_client import login, new_game

FORM_HEADER = """\
[bold cyan]── 开始新游戏 ──────────────────────────────────────[/]

填写以下信息后按 [bold]Enter[/] 确认，[bold]Escape[/] 返回主菜单。
"""


class NewGameScreen(Screen[None]):
    """新游戏表单 Screen：填写 user_name 和 game_name 后创建游戏。"""

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

    def compose(self) -> ComposeResult:
        yield RichLog(id="form-log", highlight=True, markup=True, wrap=True)
        yield Label("用户名 (user_name)：", id="username-label")
        yield Input(
            value=f"player_{int(time.time())}",
            placeholder="用户名",
            id="username-input",
        )
        yield Label("游戏名 (game_name)：", id="gamename-label")
        yield Input(
            value="Game1",
            placeholder="游戏名",
            id="gamename-input",
        )
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(FORM_HEADER)
        self.query_one("#username-input", Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Input.Submitted, "#username-input")
    def focus_gamename(self, event: Input.Submitted) -> None:
        self.query_one("#gamename-input", Input).focus()

    @on(Input.Submitted, "#gamename-input")
    def submit_form(self, event: Input.Submitted) -> None:
        user_name = self.query_one("#username-input", Input).value.strip()
        game_name = self.query_one("#gamename-input", Input).value.strip()

        if not user_name:
            self.query_one(RichLog).write("[red]用户名不能为空[/]")
            self.query_one("#username-input", Input).focus()
            return
        if not game_name:
            self.query_one(RichLog).write("[red]游戏名不能为空[/]")
            return

        self._start_new_game(user_name, game_name)

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
