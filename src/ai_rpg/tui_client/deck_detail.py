"""牌组详情 Screen"""

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
from .utils import display_name
from ..models import ArchetypeComponent, DeckComponent

_TARGET_LABEL = {
    "enemy_single": "[red]敌方单体[/]",
    "enemy_all": "[red]敌方全体[/]",
    "ally_single": "[green]友方单体[/]",
    "ally_all": "[green]友方全体[/]",
    "self_only": "[cyan]仅自己[/]",
}

DECK_HEADER = """\
[bold cyan]── 牌组详情 ──────────────────────────────────────[/]

显示本次地下城各角色历史牌组（出牌 + 回合结束归还）。[bold]Escape[/] 返回。
"""


class DeckDetailScreen(Screen[None]):
    """牌组详情 Screen：显示各角色 DeckComponent.cards 完整列表（只读）。"""

    CSS = """
    DeckDetailScreen {
        align: center middle;
    }

    #deck-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield RichLog(id="deck-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(DECK_HEADER)
        self._fetch_deck()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @work
    async def _fetch_deck(self) -> None:
        """获取并渲染各角色牌组信息。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载牌组信息...[/]")
        logger.info("DeckDetailScreen._fetch_deck")

        try:
            from .app import GameClient

            app: GameClient = self.app  # type: ignore[assignment]
            if app.session is None:
                return

            room_resp = await fetch_dungeon_room(
                app.session.user_name, app.session.game_name
            )
            stage_name = room_resp.room.stage.name

            stages_resp = await fetch_stages_state(
                app.session.user_name, app.session.game_name
            )
            actor_names = stages_resp.mapping.get(stage_name, [])

            if not actor_names:
                log.write("  [dim]（当前场景无角色数据）[/]")
                return

            details_resp = await fetch_entities_details(
                app.session.user_name, app.session.game_name, actor_names
            )

            log.write(
                f"[bold yellow]场景：{display_name(stage_name)}  共 {len(details_resp.entities_serialization)} 个实体[/]"
            )
            log.write("")

            for entity in details_resp.entities_serialization:
                deck_raw = next(
                    (c for c in entity.components if c.name == "DeckComponent"), None
                )
                if deck_raw is None:
                    continue

                deck = DeckComponent(**deck_raw.data)
                card_count = len(deck.cards)
                log.write(
                    f"[bold cyan]{display_name(entity.name)}[/]  "
                    f"[dim]牌组共 {card_count} 张[/]"
                )

                # 1) 卡牌列表
                if card_count == 0:
                    log.write("  [dim]（尚无记录）[/]")
                else:
                    for i, card in enumerate(deck.cards, start=1):
                        hit_str = (
                            f"x[yellow]{card.hit_count}[/]"
                            if card.hit_count > 1
                            else ""
                        )
                        tt_str = _TARGET_LABEL.get(
                            card.target_type, f"[dim]{card.target_type}[/]"
                        )
                        action_str = (
                            f"\n        [dim]{card.description}[/]"
                            if card.description
                            else ""
                        )
                        hint_str = (
                            f"\n        [yellow]副作用暗示：{card.status_effect_hint}[/]"
                            if card.status_effect_hint
                            else ""
                        )
                        source_str = (
                            f"  [dim]来源:{display_name(card.source)}[/]"
                            if card.source and card.source != entity.name
                            else ""
                        )
                        log.write(
                            f"  [bold green]{i:>2}[/]  [bold]{card.name}[/]  "
                            f"伤害:[red]{card.damage_dealt}[/]{hit_str}  "
                            f"格挡:[blue]{card.block_gain}[/]  目标:{tt_str}"
                            + source_str
                            + action_str
                            + hint_str
                        )

                # 2) Archetype 原型约束（卡牌列表之后）
                archetype_raw = next(
                    (c for c in entity.components if c.name == "ArchetypeComponent"),
                    None,
                )
                if archetype_raw is not None:
                    archetype_comp = ArchetypeComponent(**archetype_raw.data)
                    if archetype_comp.archetypes:
                        log.write("")
                        for j, arch in enumerate(archetype_comp.archetypes, start=1):
                            log.write(
                                f"  [bold magenta]原型 {j}：[/][dim]{arch.description}[/]"
                            )

                log.write("")

            logger.info(
                f"DeckDetailScreen._fetch_deck: 加载完成 entities={len(details_resp.entities_serialization)}"
            )
        except Exception as e:
            logger.error(f"DeckDetailScreen._fetch_deck: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载牌组信息失败: {e}[/]")
