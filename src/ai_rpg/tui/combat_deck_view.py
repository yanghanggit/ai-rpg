"""查阅牌组（双方）Screen（CombatDeckViewScreen）

INITIALIZATION 阶段命令 2）的详情页：展示战斗双方（玩家+队友 / 怪物）各自的 DeckComponent。
"""

from typing import List, final

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.widgets import RichLog

from ..models import (
    Card,
    DeckComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
)
from .base import BaseGameScreen
from .combat_common import find_component_data
from .combat_data_access import get_entities_details
from .utils import display_name, render_card

HEADER = """\
[bold cyan]── 查阅牌组（双方） ──────────────────────────────────────[/]

[dim]Escape 返回。[/]
"""


def _render_pile(log: RichLog, label: str, cards: List[Card]) -> None:
    """渲染一个战斗子牌堆（抽牌堆/消耗堆/弃牌堆）的归属数。"""
    if not cards:
        log.write(f"  {label}：[dim]（空）[/]")
        return
    log.write(f"  {label}：共 [bold]{len(cards)}[/] 张")


@final
class CombatDeckViewScreen(BaseGameScreen):
    """展示战斗全部参战者的牌组（DeckComponent）。"""

    CSS = """
    CombatDeckViewScreen {
        align: center middle;
    }

    #combat-deck-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self, participant_names: List[str]) -> None:
        super().__init__()
        self._participant_names = participant_names

    def compose(self) -> ComposeResult:
        yield RichLog(id="combat-deck-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HEADER)
        self._load_decks()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    @work
    async def _load_decks(self) -> None:
        log = self.query_one(RichLog)
        logger.info(
            f"CombatDeckViewScreen._load_decks: participants={self._participant_names}"
        )
        try:
            resp = await get_entities_details(self.game_client, self._participant_names)
        except Exception as e:
            logger.error(f"CombatDeckViewScreen._load_decks: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载牌组失败：{e}[/]")
            return

        if not resp.entities_serialization:
            log.write("[yellow]未找到任何参战者。[/]")
            return

        for entity in resp.entities_serialization:
            deck_data = find_component_data(entity, DeckComponent.__name__)
            log.write(f"[bold yellow]── {display_name(entity.name)} ──[/]")
            if deck_data is None:
                log.write("  [dim]（无牌组组件）[/]")
                log.write("")
                continue

            deck = DeckComponent(**deck_data)
            if deck.keywords:
                log.write(f"  关键词：[dim]{'、'.join(deck.keywords)}[/]")
            if not deck.cards:
                log.write("  [dim]（牌组为空）[/]")
            else:
                log.write(f"  共 [bold]{len(deck.cards)}[/] 张：")
                for card in deck.cards:
                    log.write(render_card(card))

            # 以下三个子牌堆仅在 ONGOING 阶段才存在（INITIALIZATION 阶段尚未创建），
            # 若实体不存在相应组件则跳过不显示。
            draw_pile_data = find_component_data(entity, DrawPileComponent.__name__)
            if draw_pile_data is not None:
                _render_pile(log, "抽牌堆", DrawPileComponent(**draw_pile_data).cards)

            exhaust_pile_data = find_component_data(
                entity, ExhaustPileComponent.__name__
            )
            if exhaust_pile_data is not None:
                _render_pile(
                    log, "消耗堆", ExhaustPileComponent(**exhaust_pile_data).cards
                )

            discard_pile_data = find_component_data(
                entity, DiscardPileComponent.__name__
            )
            if discard_pile_data is not None:
                _render_pile(
                    log, "弃牌堆", DiscardPileComponent(**discard_pile_data).cards
                )

            log.write("")
