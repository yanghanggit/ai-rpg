"""查阅战利品 Screen（CombatLootViewScreen）

战斗结算（COMPLETE / POST_COMBAT 阶段）查阅玩家身上的 CombatLootComponent
（本场战斗从怪物处获得的战利品，实践中为 MaterialItem），并支持收取战利品——
调用 /api/dungeon/combat/collect_loot/v1/（服务端 collect_combat_loot），将战利品
转入随身背包（InventoryComponent）并移除 CombatLootComponent。

由 CombatPostCombatScreen 指令 6 push 至此。
"""

from typing import final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import CombatLootComponent
from .base import BaseGameScreen
from .combat_data_access import get_entities_details, is_mock_mode, resolve_identity
from .server_client import dungeon_combat_collect_loot
from .utils import display_name, render_item

HEADER = """\
[bold cyan]── 查阅战利品 ──────────────────────────────────────[/]

[dim]输入 1 收取战利品（转入随身背包）；Escape 返回。[/]
"""


@final
class CombatLootViewScreen(BaseGameScreen):
    """展示玩家身上的战斗战利品（CombatLootComponent），并支持收取。"""

    CSS = """
    CombatLootViewScreen {
        align: center middle;
    }

    #combat-loot-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-loot-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-loot-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-loot-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(id="combat-loot-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="combat-loot-input-row"):
            yield Static("> ", id="combat-loot-prompt")
            yield Input(placeholder="输入 1 收取战利品...", id="combat-loot-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HEADER)
        self._load_loot()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    @work
    async def _load_loot(self) -> None:
        """加载并渲染玩家身上的 CombatLootComponent（若不存在则说明本场无掉落或已收取）。"""
        log = self.query_one(RichLog)
        _, _, actor_name = resolve_identity(self.game_client)
        logger.info(f"CombatLootViewScreen._load_loot: actor={actor_name}")

        try:
            resp = await get_entities_details(self.game_client, [actor_name])
        except Exception as e:
            logger.error(f"CombatLootViewScreen._load_loot: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载战利品失败：{e}[/]")
            return

        if not resp.entities_serialization:
            log.write(f"[yellow]未找到角色：{actor_name}[/]")
            return

        entity = resp.entities_serialization[0]
        loot_data = next(
            (
                c.data
                for c in entity.components
                if c.name == CombatLootComponent.__name__
            ),
            None,
        )
        log.write(f"[bold yellow]── {display_name(entity.name)} 的战利品 ──[/]")
        if loot_data is None:
            log.write("  [dim]（本场战斗无战利品，或已收取）[/]")
            return

        loot = CombatLootComponent(**loot_data)
        if not loot.items:
            log.write("  [dim]（战利品为空）[/]")
            return

        log.write(f"  共 [bold]{len(loot.items)}[/] 件战利品：")
        log.write("  " + "-" * 40)
        for item in loot.items:
            log.write("  " + render_item(item))
            log.write("  " + "-" * 40)
        log.write("[bold green]输入 1 收取战利品（转入随身背包）[/]")

    ########################################################################################################################
    @on(Input.Submitted, "#combat-loot-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        if raw != "1":
            self.query_one(RichLog).write("[red]无效指令，请输入 1[/]")
            return
        self._do_collect_loot()

    ########################################################################################################################
    @work
    async def _do_collect_loot(self) -> None:
        """收取战利品：调用 /api/dungeon/combat/collect_loot/v1/，成功后重新加载展示。

        mock 模式（session 为 None，即通过 `--dev-screen` 跳过登录直接进入调试）：
        不存在真实后端会话，无法执行会改变状态的收取操作，仅提示。
        """
        log = self.query_one(RichLog)

        if is_mock_mode(self.game_client):
            logger.info("CombatLootViewScreen._do_collect_loot: mock 模式，跳过收取")
            log.write("[dim]mock 模式：无真实会话，无法收取战利品[/]")
            return

        inp = self.query_one(Input)
        inp.disabled = True
        log.write("[dim]▶ 正在收取战利品...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_combat_collect_loot(user_name, game_name)
        except Exception as e:
            logger.error(f"CombatLootViewScreen._do_collect_loot: 收取失败 error={e}")
            log.write(f"[bold red]❌ 收取战利品失败：{e}[/]")
            inp.disabled = False
            inp.focus()
            return

        log.write(f"[bold green]✅ {resp.message}[/]")
        logger.info(
            f"CombatLootViewScreen._do_collect_loot: 收取成功 message={resp.message}"
        )

        inp.disabled = False
        inp.focus()
        self._load_loot()
