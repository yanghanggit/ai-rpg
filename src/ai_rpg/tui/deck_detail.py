"""牌组详情 Screen"""

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.widgets import RichLog
from .base import BaseGameScreen
from .server_client import (
    fetch_dungeon_room,
    fetch_entities_details,
    fetch_stages_state,
)
from .utils import display_name
from ..models import (
    DeckComponent,
    HandComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    DiscardPileComponent,
)
from .combat_room_renderer import write_hand_table

DECK_HEADER = """\
[bold cyan]── 牌组详情 ──────────────────────────────────────[/]

显示本次地下城各角色牌组（已出牌 / 弃牌堆 / 可重抽）。[bold]Escape[/] 返回。
"""


class DeckDetailScreen(BaseGameScreen):
    """牌组详情 Screen：分节展示各角色 DiscardPileComponent（已出牌）和 DrawPileComponent（可重抽）和 ExhaustPileComponent（弃牌堆）。"""

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
            app = self.game_client
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
                discard_raw = next(
                    (
                        c
                        for c in entity.components
                        if c.name == ExhaustPileComponent.__name__
                    ),
                    None,
                )
                draw_raw = next(
                    (
                        c
                        for c in entity.components
                        if c.name == DrawPileComponent.__name__
                    ),
                    None,
                )
                played_raw = next(
                    (
                        c
                        for c in entity.components
                        if c.name == DiscardPileComponent.__name__
                    ),
                    None,
                )
                deck_raw = next(
                    (c for c in entity.components if c.name == DeckComponent.__name__),
                    None,
                )
                if (
                    discard_raw is None
                    and draw_raw is None
                    and played_raw is None
                    and deck_raw is None
                ):
                    continue

                discard_comp = (
                    ExhaustPileComponent(**discard_raw.data) if discard_raw else None
                )
                draw_comp = DrawPileComponent(**draw_raw.data) if draw_raw else None
                played_comp = (
                    DiscardPileComponent(**played_raw.data) if played_raw else None
                )
                deck_comp = DeckComponent(**deck_raw.data) if deck_raw else None
                discard_count = len(discard_comp.cards) if discard_comp else 0
                draw_count = len(draw_comp.cards) if draw_comp else 0
                played_count = len(played_comp.cards) if played_comp else 0
                deck_count = len(deck_comp.cards) if deck_comp else 0

                hand_raw = next(
                    (c for c in entity.components if c.name == HandComponent.__name__),
                    None,
                )
                hand_comp = HandComponent(**hand_raw.data) if hand_raw else None
                hand_suffix = (
                    f" | 手牌 {len(hand_comp.cards)} 张"
                    if hand_comp is not None
                    else ""
                )

                log.write(
                    f"[bold cyan]{display_name(entity.name)}[/]  "
                    f"[dim]牌库 {deck_count} 张 | 已出牌 {played_count} 张 | 消耗堆 {discard_count} 张 | 可重抽 {draw_count} 张{hand_suffix}[/]"
                )

                # 0) 牌库（DeckComponent）
                log.write("[dim]──────────────────────────────────────────────────[/]")
                log.write("  [bold blue]▸ 牌库（DeckComponent）[/]")
                if deck_comp and deck_comp.cards:
                    write_hand_table(log, deck_comp.cards, entity.name)
                else:
                    log.write("    [dim]（尚无记录）[/]")

                # 1) 已出牌（DiscardPile）
                log.write("[dim]──────────────────────────────────────────────────[/]")
                log.write("  [bold red]▸ 已出牌（DiscardPile）[/]")
                if played_comp and played_comp.cards:
                    write_hand_table(log, played_comp.cards, entity.name)
                else:
                    log.write("    [dim]（尚无记录）[/]")

                # 2) 消耗堆（ExhaustPile）
                log.write("[dim]──────────────────────────────────────────────────[/]")
                log.write("  [bold magenta]▸ 消耗堆（ExhaustPile）[/]")
                if discard_comp and discard_comp.cards:
                    write_hand_table(log, discard_comp.cards, entity.name)
                else:
                    log.write("    [dim]（尚无记录）[/]")

                # 3) 可重抽卡牌（DrawPile）
                log.write("[dim]──────────────────────────────────────────────────[/]")
                log.write("  [bold yellow]▸ 可重抽（DrawPile）[/]")
                if draw_comp and draw_comp.cards:
                    write_hand_table(log, draw_comp.cards, entity.name)
                else:
                    log.write("    [dim]（尚无记录）[/]")

                # 4) 当前手牌（HandComponent，可选）
                if hand_comp is not None:
                    log.write(
                        "[dim]──────────────────────────────────────────────────[/]"
                    )
                    # log.write(
                    #     f"  [bold green]▸ 当前手牌（HandComponent，回合 {hand_comp.round}）[/]"
                    # )
                    if hand_comp.cards:
                        write_hand_table(log, hand_comp.cards, entity.name)
                    else:
                        log.write("    [dim]（手牌为空）[/]")

                # 5) Keyword 关键词约束
                if deck_comp and deck_comp.keywords:
                    log.write(
                        "[dim]──────────────────────────────────────────────────[/]"
                    )
                    log.write("  [bold magenta]▸ 关键词约束[/]")
                    for j, kw in enumerate(deck_comp.keywords, start=1):
                        log.write(f"  [bold magenta]关键词 {j}：[/][dim]{kw}[/]")

                log.write(
                    "[bold cyan]══════════════════════════════════════════════════[/]"
                )
                log.write("")

            logger.info(
                f"DeckDetailScreen._fetch_deck: 加载完成 entities={len(details_resp.entities_serialization)}"
            )
        except Exception as e:
            logger.error(f"DeckDetailScreen._fetch_deck: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载牌组信息失败: {e}[/]")
