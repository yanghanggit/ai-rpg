"""查阅卡池 Screen（CombatCardPoolViewScreen）

开场房间的详情页：展示我方队伍成员的 CardPoolComponent（抽卡候选）。
通过现有实体详情 API 拉取数据，再反序列化成 CardPoolComponent 渲染。
"""

from typing import List, final

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.widgets import RichLog

from ..models import CardPoolComponent
from .base import BaseGameScreen
from .combat_common import find_component_data
from .combat_data_access import get_entities_details
from .utils import display_name, render_card

HEADER = """\
[bold cyan]── 查阅卡池（我方） ──────────────────────────────────────[/]

[dim]Escape 返回。[/]
"""


@final
class CombatCardPoolViewScreen(BaseGameScreen):
    """展示我方队伍成员的卡池（CardPoolComponent，抽卡候选）。"""

    CSS = """
    CombatCardPoolViewScreen {
        align: center middle;
    }

    #card-pool-log {
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
        yield RichLog(id="card-pool-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HEADER)
        self._load_card_pools()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    @work
    async def _load_card_pools(self) -> None:
        log = self.query_one(RichLog)
        logger.info(
            f"CombatCardPoolViewScreen._load_card_pools: participants={self._participant_names}"
        )
        try:
            resp = await get_entities_details(self.game_client, self._participant_names)
        except Exception as e:
            logger.error(
                f"CombatCardPoolViewScreen._load_card_pools: 加载失败 error={e}"
            )
            log.write(f"[bold red]❌ 加载卡池失败：{e}[/]")
            return

        if not resp.entities:
            log.write("[yellow]未找到任何参战者。[/]")
            return

        for entity in resp.entities:
            pool_data = find_component_data(entity, CardPoolComponent.__name__)
            log.write(f"[bold yellow]── {display_name(entity.name)} ──[/]")
            if pool_data is None:
                log.write("  [dim]（无卡池组件，请先执行「生成卡池」）[/]")
                log.write("")
                continue

            pool = CardPoolComponent(**pool_data)
            if not pool.cards:
                log.write("  [dim]（卡池为空）[/]")
            else:
                log.write(f"  候选卡 [bold]{len(pool.cards)}[/] 张：")
                for card in pool.cards:
                    log.write(render_card(card))

            log.write("")
