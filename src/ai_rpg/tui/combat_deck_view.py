"""查阅牌组（双方）Screen（CombatDeckViewScreen）

INITIALIZATION 阶段命令 2）的详情页：展示战斗双方（玩家+队友 / 怪物）各自的 DeckComponent。
"""

from typing import List, final

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.widgets import RichLog

from ..models import Card, DeckComponent
from .base import BaseGameScreen
from .combat_data_access import get_entities_details
from .utils import display_name

HEADER = """\
[bold cyan]── 查阅牌组（双方） ──────────────────────────────────────[/]

[dim]Escape 返回。[/]
"""


def _render_card(card: Card) -> str:
    exhaust_mark = "[dim]（消耗）[/]" if card.exhaust else ""
    return (
        f"    [bold]{card.name}[/]{exhaust_mark}  "
        f"费用:{card.cost}  伤害:{card.damage_dealt}  连击:{card.hit_count}\n"
        f"      [dim]{card.description}[/]"
    )


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
            deck_data = next(
                (c.data for c in entity.components if c.name == DeckComponent.__name__),
                None,
            )
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
                    log.write(_render_card(card))
            log.write("")
