"""查阅卡池 / 挑选卡牌 Screen（CombatCardPoolViewScreen）

开场房间的详情页：展示我方队伍成员的 CardPoolComponent（抽卡候选），
并支持输入卡牌名从玩家自己的卡池中挑选一张加入牌库。
通过现有实体详情 API 拉取数据，再反序列化成 CardPoolComponent 渲染。
"""

from typing import List, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import CardPoolComponent
from .base import BaseGameScreen
from .combat_common import find_component_data
from .combat_data_access import get_entities_details, resolve_identity
from .server_client import (
    TaskFailedError,
    dungeon_opening_pick_card_from_pool,
    watch_task_until_done,
)
from .utils import display_name, render_card

HEADER = """\
[bold cyan]── 查阅卡池 / 挑选卡牌（我方） ───────────────────────[/]

[dim]输入卡牌名挑选一张加入自己的牌库，Escape 返回。[/]
"""


@final
class CombatCardPoolViewScreen(BaseGameScreen):
    """展示我方队伍成员的卡池（CardPoolComponent，抽卡候选），并支持挑卡。"""

    CSS = """
    CombatCardPoolViewScreen {
        align: center middle;
    }

    #card-pool-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #card-pool-input-row {
        height: 3;
        dock: bottom;
    }

    #card-pool-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #card-pool-input {
        width: 1fr;
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
        with Horizontal(id="card-pool-input-row"):
            yield Static("> ", id="card-pool-prompt")
            yield Input(placeholder="输入卡牌名挑选...", id="card-pool-input")

    def on_mount(self) -> None:
        self._refresh()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    def _refresh(self) -> None:
        """清屏并重新加载卡池。"""
        log = self.query_one(RichLog)
        log.clear()
        log.write(HEADER)
        self._load_card_pools()

    ########################################################################################################################
    @on(Input.Submitted, "#card-pool-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        self._pick_card(raw)

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

    ########################################################################################################################
    @work
    async def _pick_card(self, card_name: str) -> None:
        """从玩家自己的卡池挑选一张卡加入牌库。"""
        log = self.query_one(RichLog)
        logger.info(f"CombatCardPoolViewScreen._pick_card: card={card_name}")
        log.write(f"[dim]正在挑选卡牌「{card_name}」，请稍候...[/]")

        try:
            user_name, game_name, actor_name = resolve_identity(self.game_client)
            resp = await dungeon_opening_pick_card_from_pool(
                user_name, game_name, actor_name, card_name
            )
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            record = await watch_task_until_done(resp.task_id)
            log.write(f"[bold green]✅ 挑卡完成：{record.status}[/]")
            log.write(f"[dim]已把「{card_name}」加入牌库。[/]")
            self._refresh()
        except TaskFailedError as e:
            logger.error(f"CombatCardPoolViewScreen._pick_card: 任务失败 error={e}")
            log.write(f"[bold red]❌ 挑卡失败：{e}[/]")
        except Exception as e:
            logger.error(f"CombatCardPoolViewScreen._pick_card: 请求失败 error={e}")
            log.write(f"[bold red]❌ 请求失败：{e}[/]")
