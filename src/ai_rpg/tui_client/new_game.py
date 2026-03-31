"""新游戏 Screen"""

from datetime import datetime
from typing import List
from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog
from ..models import Blueprint
from .server_client import fetch_blueprint_list, login, new_game


class NewGameScreen(Screen[None]):
    """新游戏 Screen：自动生成玩家 ID，展示第一个蓝图详情，按 Enter 开始游戏。"""

    CSS = """
    NewGameScreen {
        align: center middle;
    }

    #form-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("enter", "start_game", "Start"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._blueprints: List[Blueprint] = []
        self._player_id = f"player_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._starting = False

    def compose(self) -> ComposeResult:
        yield RichLog(id="form-log", highlight=True, markup=True, wrap=True)

    # yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(
            "[bold cyan]── 开始新游戏 ──────────────────────────────────────[/]\n"
        )
        log.write(f"玩家 ID：[bold green]{self._player_id}[/]\n")
        self._load_blueprints()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_start_game(self) -> None:
        if self._starting:
            return
        if not self._blueprints:
            self.query_one(RichLog).write("[yellow]⚠ 蓝图尚未加载完成，请稍候...[/]")
            return
        self._starting = True
        self._start_new_game(self._player_id, self._blueprints[0].name)

    @work
    async def _load_blueprints(self) -> None:
        log = self.query_one(RichLog)
        logger.info("_load_blueprints: 正在获取蓝图列表...")
        try:
            resp = await fetch_blueprint_list()
            self._blueprints = resp.blueprints
            if self._blueprints:
                bp = self._blueprints[0]
                log.write(
                    "[bold cyan]── 游戏蓝图 ──────────────────────────────────[/]"
                )
                log.write(f"[bold green]{bp.name}[/]")
                log.write(f"\n{bp.campaign_setting}\n")

                log.write(
                    "[bold cyan]── 玩家角色 ──────────────────────────────────[/]"
                )
                log.write(f"  [bold magenta]{bp.player_actor}[/]\n")

                log.write(
                    "[bold cyan]── 场景与角色 ────────────────────────────────[/]"
                )
                for stage in bp.stages:
                    actor_names = [a.name for a in stage.actors]
                    if actor_names:
                        actors_str = "、".join(
                            f"[{'bold magenta' if a == bp.player_actor else 'green'}]{a}[/]"
                            for a in actor_names
                        )
                        log.write(f"  [bold cyan]{stage.name}[/] → {actors_str}")
                    else:
                        log.write(f"  [bold cyan]{stage.name}[/] → [dim]（空）[/]")
                log.write("")
                log.write(
                    "[dim]按 [bold]Enter[/] 进入游戏，[bold]Escape[/] 返回主菜单。[/]"
                )
            else:
                log.write("[red]❌ 服务器暂无可用蓝图，无法开始游戏。[/]")
            logger.info(
                f"_load_blueprints: 获取成功，共 {len(self._blueprints)} 个蓝图"
            )
        except Exception as e:
            logger.error(f"_load_blueprints: 获取失败 error={e}")
            log.write(f"[red]❌ 蓝图列表获取失败：{e}[/]")

    @work
    async def _start_new_game(self, user_name: str, game_name: str) -> None:
        log = self.query_one(RichLog)
        log.write(f"\n[dim]正在登录，player_id={user_name} ...[/]")
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
            self._starting = False
            return

        log.write(f"[dim]正在创建游戏，game_name={game_name} ...[/]")
        logger.info(f"_start_new_game: 开始创建游戏 game_name={game_name}")
        try:
            resp = await new_game(user_name, game_name)
            log.write(f"[bold green]✅ 游戏已创建！正在进入...[/]")
            logger.info(
                f"_start_new_game: 游戏创建成功 user_name={user_name} game_name={game_name} → 进入 HomeScreen"
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
            self._starting = False
