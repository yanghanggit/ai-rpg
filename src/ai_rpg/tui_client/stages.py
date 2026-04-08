"""场景总览 Screen（场景分布 + 当前场景描述）"""

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog

from .server_client import fetch_entities_details, fetch_stages_state
from .utils import display_name

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

    def __init__(self) -> None:
        super().__init__()

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

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name
        bp = app.session.blueprint
        player_actor = bp.player_actor

        logger.info(
            f"StagesScreen._load_stages_and_desc: user_name={user_name} game_name={game_name}"
        )

        # ── 1. 场景分布 ────────────────────────────────
        try:
            stages_resp = await fetch_stages_state(user_name, game_name)
        except Exception as e:
            logger.error(f"StagesScreen: fetch_stages_state 失败 error={e}")
            log.write(f"[bold red]❌ 场景状态查询失败: {e}[/]")
            return

        all_stage_names = list(stages_resp.mapping.keys())

        # ── 2. 一次性获取全部场景实体详情（PlayerOnlyStageComponent + 场景描述） ──
        player_only_stages: set[str] = set()
        stage_narratives: dict[str, str] = {}
        if all_stage_names:
            try:
                entities_resp = await fetch_entities_details(
                    user_name, game_name, all_stage_names
                )
                for entity in entities_resp.entities_serialization:
                    for comp in entity.components:
                        if comp.name == "PlayerOnlyStageComponent":
                            player_only_stages.add(entity.name)
                        elif comp.name == "StageDescriptionComponent":
                            narrative = comp.data.get("narrative", "")
                            if narrative:
                                stage_narratives[entity.name] = narrative
            except Exception as e:
                logger.warning(f"StagesScreen: fetch_entities_details 失败 error={e}")

        log.write(
            "[bold yellow]── 场景与角色分布 ──────────────────────────────────────[/]"
        )
        current_stage: str = ""
        if not stages_resp.mapping:
            log.write("  [dim]（暂无场景数据）[/]")
        else:
            for stage, actors in stages_resp.mapping.items():
                actors_str = (
                    "、".join(display_name(a) for a in actors)
                    if actors
                    else "[dim]（空）[/]"
                )
                if stage in player_only_stages:
                    log.write(
                        f"  [bold magenta]{display_name(stage)} ★玩家专属场景[/] → {actors_str}"
                    )
                else:
                    log.write(f"  [bold cyan]{display_name(stage)}[/] → {actors_str}")
                # 定位玩家当前场景
                if player_actor and player_actor in actors:
                    current_stage = stage
        log.write("")

        # ── 3. 当前场景描述 ────────────────────────────────
        if not player_actor:
            log.write("[dim]玩家角色信息不可用，无法展示场景描述。[/]")
            return

        if not current_stage:
            log.write(
                f"[yellow]⚠ 未能找到玩家角色 {display_name(player_actor)} 所在场景[/]"
            )
            return

        log.write(
            f"[bold yellow]── 场景描述：{display_name(current_stage)} ──────────────────────────────────────[/]"
        )
        narrative = stage_narratives.get(current_stage, "")
        if narrative:
            log.write(narrative)
        else:
            log.write("[dim]（场景描述尚未生成）[/]")
        log.write("")
        logger.info(
            f"StagesScreen: 加载完成 current_stage={current_stage} narrative_len={len(narrative)}"
        )
