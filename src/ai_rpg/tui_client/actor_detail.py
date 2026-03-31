"""角色详情 Screen"""

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog

from .server_client import (
    fetch_dungeon_room,
    fetch_entities_details,
    fetch_stages_state,
)
from ..models import (
    AllyComponent,
    CharacterStatsComponent,
    EnemyComponent,
    HandComponent,
    PlayerComponent,
    StatusEffectsComponent,
)

DETAIL_HEADER = """\
[bold cyan]── 角色详情 ──────────────────────────────────────[/]

显示当前房间所有角色的完整属性与状态效果。[bold]Escape[/] 返回。
"""


class ActorDetailScreen(Screen[None]):
    """角色详情 Screen：显示当前房间所有角色的完整 ECS 组件信息（只读）。"""

    CSS = """
    ActorDetailScreen {
        align: center middle;
    }

    #detail-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name

    def compose(self) -> ComposeResult:
        yield RichLog(id="detail-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(DETAIL_HEADER)
        self._fetch_detail()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @work
    async def _fetch_detail(self) -> None:
        """获取当前房间所有角色的完整 ECS 组件信息。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载角色详情...[/]")
        logger.info(
            f"ActorDetailScreen._fetch_detail: user={self._user_name} game={self._game_name}"
        )

        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            stage = room_resp.room.stage

            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            actor_names = stages_resp.mapping.get(stage.name, [])

            if not actor_names:
                log.write("  [dim]（房间内无角色）[/]")
                return

            details_resp = await fetch_entities_details(
                self._user_name, self._game_name, actor_names
            )

            for entity in details_resp.entities_serialization:
                # 阵营检测 + 玩家标记
                faction = "[dim]未知[/]"
                is_player = any(
                    c.name == PlayerComponent.__name__ for c in entity.components
                )
                for comp in entity.components:
                    if comp.name == AllyComponent.__name__:
                        faction = "[bold green]友方[/]"
                        break
                    elif comp.name == EnemyComponent.__name__:
                        faction = "[bold red]敌方[/]"
                        break

                player_tag = "  [bold yellow]\[玩家][/]" if is_player else ""
                log.write(
                    f"[bold cyan]── {faction} [bold]{entity.name}[/]{player_tag} ──[/]"
                )

                # 战斗属性
                stats_comp = next(
                    (
                        c
                        for c in entity.components
                        if c.name == CharacterStatsComponent.__name__
                    ),
                    None,
                )
                if stats_comp is not None:
                    stats = stats_comp.data.get("stats", {})
                    hp = stats.get("hp", "?")
                    max_hp = stats.get("max_hp", "?")
                    attack = stats.get("attack", "?")
                    defense = stats.get("defense", "?")
                    log.write(
                        f"  HP:[yellow]{hp}/{max_hp}[/]"
                        f"  ATK:[red]{attack}[/]"
                        f"  DEF:[blue]{defense}[/]"
                    )
                else:
                    log.write("  [dim](无战斗属性)[/]")

                # 状态效果
                status_effects_comp = next(
                    (
                        c
                        for c in entity.components
                        if c.name == StatusEffectsComponent.__name__
                    ),
                    None,
                )
                if status_effects_comp is not None:
                    status_effects = status_effects_comp.data.get("status_effects", [])
                    if status_effects:
                        log.write(f"  [bold]状态效果（{len(status_effects)}）：[/]")
                        for effect in status_effects:
                            if isinstance(effect, dict):
                                name = effect.get("name", "?")
                                category = effect.get("category", "?")
                                manifestation = effect.get("manifestation", "?")
                                effect_val = effect.get("effect", "?")
                                log.write(
                                    f"    └ [magenta]{name}[/]  [{category}]"
                                    f"  {manifestation}  {effect_val}"
                                )
                            else:
                                log.write(f"    └ [magenta]{str(effect)}[/]")
                    else:
                        log.write("  [dim](无状态效果)[/]")
                else:
                    log.write("  [dim](无状态效果)[/]")

                # 手牌
                hand_comp = next(
                    (c for c in entity.components if c.name == HandComponent.__name__),
                    None,
                )
                if hand_comp is not None:
                    cards = hand_comp.data.get("cards", [])
                    round_num = hand_comp.data.get("round", "?")
                    log.write(
                        f"  [bold]手牌（回合 {round_num}，共 {len(cards)} 张）：[/]"
                    )
                    if cards:
                        for card in cards:
                            if isinstance(card, dict):
                                cname = card.get("name", "?")
                                dmg = card.get("damage_dealt", 0)
                                blk = card.get("block_gain", 0)
                                action = card.get("action", "")
                                log.write(
                                    f"    └ [bold]{cname}[/]"
                                    f"  伤害:[red]{dmg}[/]"
                                    f"  格挡:[blue]{blk}[/]"
                                    + (f"  [dim]{action}[/]" if action else "")
                                )
                    else:
                        log.write("    [dim](手牌为空)[/]")

                log.write("")

            logger.info("ActorDetailScreen._fetch_detail: 加载完成")
        except Exception as e:
            logger.error(f"ActorDetailScreen._fetch_detail: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载角色详情失败: {e}[/]")
