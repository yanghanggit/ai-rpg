"""场景总览 Screen（场景分布 + 当前场景描述）"""

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog

from .server_client import fetch_entities_details, fetch_stages_state

STAGES_HEADER = """\
[bold cyan]╔══════════════════════════════════════════════════╗[/]
[bold cyan]║              场景总览                           ║[/]
[bold cyan]╚══════════════════════════════════════════════════╝[/]

[dim]按 Escape 返回主场景。[/]
"""


class StagesScreen(Screen[None]):
    """场景总览 Screen：展示全部场景角色分布，并显示玩家当前场景描述。"""

    CSS = """
    StagesScreen {
        align: center middle;
    }

    #stages-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name

    def compose(self) -> ComposeResult:
        yield RichLog(id="stages-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(STAGES_HEADER)
        self._load_stages_and_desc()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @work
    async def _load_stages_and_desc(self) -> None:
        """加载场景分布，并显示玩家当前场景的描述。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载场景数据...[/]")
        logger.info(
            f"StagesScreen._load_stages_and_desc: user_name={self._user_name} game_name={self._game_name}"
        )

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        bp = app.session_blueprint
        player_actor = bp.player_actor if bp else None
        player_only_stage = bp.player_only_stage if bp else None

        # ── 1. 场景分布 ────────────────────────────────
        try:
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
        except Exception as e:
            logger.error(f"StagesScreen: fetch_stages_state 失败 error={e}")
            log.write(f"[bold red]❌ 场景状态查询失败: {e}[/]")
            return

        log.write(
            "[bold yellow]── 场景与角色分布 ──────────────────────────────────────[/]"
        )
        current_stage: str = ""
        if not stages_resp.mapping:
            log.write("  [dim]（暂无场景数据）[/]")
        else:
            for stage, actors in stages_resp.mapping.items():
                actors_str = "、".join(actors) if actors else "[dim]（空）[/]"
                if stage == player_only_stage:
                    log.write(
                        f"  [bold magenta]{stage} ★玩家专属场景[/] → {actors_str}"
                    )
                else:
                    log.write(f"  [bold cyan]{stage}[/] → {actors_str}")
                # 定位玩家当前场景
                if player_actor and player_actor in actors:
                    current_stage = stage
        log.write("")

        # ── 2. 当前场景描述 ────────────────────────────────
        if not player_actor:
            log.write("[dim]玩家角色信息不可用，无法展示场景描述。[/]")
            return

        if not current_stage:
            log.write(f"[yellow]⚠ 未能找到玩家角色 {player_actor} 所在场景[/]")
            return

        log.write(f"[dim]正在获取场景描述：{current_stage} ...[/]")
        logger.info(f"StagesScreen: 玩家所在场景 current_stage={current_stage}")
        try:
            entities_resp = await fetch_entities_details(
                self._user_name, self._game_name, [current_stage]
            )
        except Exception as e:
            logger.error(f"StagesScreen: fetch_entities_details 失败 error={e}")
            log.write(f"[bold red]❌ 场景实体查询失败: {e}[/]")
            return

        narrative = ""
        for entity in entities_resp.entities_serialization:
            for comp in entity.components:
                if comp.name == "StageDescriptionComponent":
                    narrative = comp.data.get("narrative", "")
                    break

        log.write(
            f"[bold yellow]── 场景描述：{current_stage} ──────────────────────────────────────[/]"
        )
        if narrative:
            log.write(narrative)
        else:
            log.write("[dim]（场景描述尚未生成）[/]")
        log.write("")
        logger.info(
            f"StagesScreen: 加载完成 current_stage={current_stage} narrative_len={len(narrative)}"
        )
