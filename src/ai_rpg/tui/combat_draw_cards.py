"""战斗抽牌 Screen（CombatDrawCardsScreen）"""

from typing import List, final

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.widgets import RichLog

from ..models import HandComponent
from .base import BaseGameScreen
from .combat_common import find_component_data, role_label
from .combat_data_access import get_entities_details, is_mock_mode, resolve_identity
from .server_client import (
    TaskFailedError,
    dungeon_combat_draw_cards,
    watch_task_until_done,
)
from .utils import display_name, render_card

HEADER = """\
[bold cyan]── 抽牌 ──────────────────────────────────────[/]

[dim]正在为战斗双方全体角色激活抽牌动作，请稍候...[/]
"""


@final
class CombatDrawCardsScreen(BaseGameScreen):
    """触发全员抽牌动作，等待完成后展示战斗双方全体角色的最新手牌。"""

    CSS = """
    CombatDrawCardsScreen {
        align: center middle;
    }

    #combat-draw-cards-log {
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
        self._participant_names = list(dict.fromkeys(participant_names))

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="combat-draw-cards-log", highlight=True, markup=True, wrap=True
        )

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HEADER)
        self._do_draw_cards()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    @work
    async def _do_draw_cards(self) -> None:
        """调用抽牌接口并等待后台任务完成，成功后加载并展示双方最新手牌。"""
        log = self.query_one(RichLog)
        logger.info(
            f"CombatDrawCardsScreen._do_draw_cards: participants={self._participant_names}"
        )

        if is_mock_mode(self.game_client):
            logger.info(
                "CombatDrawCardsScreen._do_draw_cards: mock 模式，跳过真实抽牌接口，"
                "直接展示 mock_data 中固定的已抽到手牌"
            )
            log.write("[bold yellow]\\[mock][/] 已模拟触发全员抽牌（未调用真实接口）。")
            log.write("[bold green]✅ 抽牌完成[/]")
            log.write("")
            await self._load_hands()
            return

        log.write("[dim]▶ 正在为全体角色抽牌...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_combat_draw_cards(user_name, game_name)
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            await watch_task_until_done(resp.task_id)
        except TaskFailedError as e:
            logger.error(
                f"CombatDrawCardsScreen._do_draw_cards: 抽牌任务失败 error={e}"
            )
            log.write(f"[bold red]❌ 抽牌失败：{e}[/]")
            return
        except Exception as e:
            logger.error(
                f"CombatDrawCardsScreen._do_draw_cards: 抽牌请求失败 error={e}"
            )
            log.write(f"[bold red]❌ 抽牌请求失败：{e}[/]")
            return

        log.write("[bold green]✅ 抽牌完成[/]")
        log.write("")
        await self._load_hands()

    ########################################################################################################################
    async def _load_hands(self) -> None:
        """加载并渲染战斗双方全体角色（participant_names）的最新手牌。"""
        log = self.query_one(RichLog)

        if not self._participant_names:
            log.write("[yellow]当前战斗暂无参战角色。[/]")
            return

        try:
            resp = await get_entities_details(self.game_client, self._participant_names)
        except Exception as e:
            logger.error(f"CombatDrawCardsScreen._load_hands: 加载手牌失败 error={e}")
            log.write(f"[bold red]❌ 加载手牌失败：{e}[/]")
            return

        entity_map = {
            entity.name: entity
            for entity in resp.entities_serialization
            if entity.name in self._participant_names
        }

        log.write("[bold yellow]── 双方手牌 ─────────────────────────────────[/]")
        for i, actor_name in enumerate(self._participant_names):
            if i > 0:
                log.write("")
            entity = entity_map.get(actor_name)
            if entity is None:
                log.write(f"[yellow]未找到参战角色：{display_name(actor_name)}[/]")
                continue

            log.write(f"{role_label(entity)} [bold]{display_name(entity.name)}[/]")

            hand_data = find_component_data(entity, HandComponent.__name__)
            if hand_data is None:
                log.write("  [dim]（无手牌组件）[/]")
                continue

            hand = HandComponent(**hand_data)
            if not hand.cards:
                log.write("  [dim]（手牌为空）[/]")
                continue

            log.write(f"  手牌（{len(hand.cards)}）：")
            for card in hand.cards:
                log.write(render_card(card))

        log.write("")
        log.write("[dim]Escape 返回。[/]")
