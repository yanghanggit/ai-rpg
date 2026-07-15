"""战斗结束处理 Screen（CombatPostCombatScreen）

CombatState.COMPLETE / POST_COMBAT 阶段的专属页面。复用 CombatOngoingScreen 的
基础信息展示（战斗宏观状态 / 回合信息 / 场景内角色有效属性）与查阅型（GET）指令
入口（查阅牌组 / 查阅背包 / 查阅指定实体信息 / 查阅历史回合详情）。
真正的战斗结算处理（胜负结果、战利品收取、退出地下城等）后续逐步补充。

由 CombatOngoingScreen 在检测到战斗进入 COMPLETE / POST_COMBAT 阶段后，通过
指令 5 push 至此。
"""

from typing import List, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import CombatRoom
from .base import BaseGameScreen
from .combat_common import (
    find_stage_of_actor,
    render_combat_summary,
    render_stage_actors,
)
from .combat_data_access import (
    get_dungeon_room,
    get_entities_details,
    get_stages_state,
    is_mock_mode,
    resolve_identity,
)
from .combat_deck_view import CombatDeckViewScreen
from .combat_entity_inspect import CombatEntityInspectScreen
from .combat_inventory_view import CombatInventoryViewScreen
from .combat_loot_view import CombatLootViewScreen
from .combat_round_history import CombatRoundHistoryScreen
from .server_client import dungeon_exit
from .home import HomeScreen

BASE_INFO_HEADER = """\
[bold cyan]── 结束战斗 ──────────────────────────────────────[/]

[dim]战斗结算（胜负结果 / 战利品收取 / 退出地下城等）开发中；当前显示基础信息。[/]
"""

POST_COMBAT_COMMANDS_MENU = """\
[bold yellow]── 可用操作 ─────────[/]
  [bold green]1[/]  查阅牌组（双方）
  [bold green]2[/]  查阅我方背包
  [bold green]3[/]  查阅指定实体信息（场景 / 角色）
  [bold green]4[/]  查阅历史回合详情
  [bold green]5[/]  退出地下城，返回家园
  [bold green]6[/]  查阅战利品
"""


@final
class CombatPostCombatScreen(BaseGameScreen):
    """战斗 COMPLETE / POST_COMBAT 阶段页面：展示基础信息，并提供查阅型（GET）指令入口。"""

    CSS = """
    CombatPostCombatScreen {
        align: center middle;
    }

    #combat-post-combat-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-post-combat-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-post-combat-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-post-combat-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="combat-post-combat-log", highlight=True, markup=True, wrap=True
        )
        with Horizontal(id="combat-post-combat-input-row"):
            yield Static("> ", id="combat-post-combat-prompt")
            yield Input(placeholder="输入指令编号...", id="combat-post-combat-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(BASE_INFO_HEADER)
        self._load_base_info()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        """返回上一页；若 session 为 None（说明本页是通过
        `--dev-screen combat-post-combat` 直接作为入口页面启动的，跳过了登录流程，
        不存在可返回的上一页），改为直接退出应用，避免 pop_screen 后停留在无法
        交互的空白默认页面。"""
        if self.game_client.session is None:
            self.app.exit()
            return
        self.app.pop_screen()

    ########################################################################################################################
    @work
    async def _load_base_info(self) -> None:
        """加载并渲染战斗宏观状态 + 回合信息 + 场景内角色有效属性（含手牌/状态效果数量）。"""
        log = self.query_one(RichLog)
        logger.info("CombatPostCombatScreen._load_base_info: 开始加载")

        try:
            _, _, actor_name = resolve_identity(self.game_client)

            room_resp = await get_dungeon_room(self.game_client)
            stages_resp = await get_stages_state(self.game_client)

            room = room_resp.room
            assert isinstance(
                room, CombatRoom
            ), f"当前房间不是战斗房间：type={room.type}"
            assert room.type == "combat"
            combat = room.combat

            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert (
                stage_name is not None
            ), f"未能在场景映射中找到玩家角色所在场景：actor={actor_name}"
            actor_names = stages_resp.mapping[stage_name]
            entity_names = [stage_name, *actor_names]

            entities_resp = await get_entities_details(self.game_client, entity_names)

        except Exception as e:
            logger.error(f"CombatPostCombatScreen._load_base_info: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载战斗基础信息失败：{e}[/]")
            return

        render_combat_summary(
            log,
            combat.name,
            combat.state.name,
            combat.result.name,
            combat.retreated,
            total_rounds=len(combat.rounds),
        )
        render_stage_actors(log, stage_name, entities_resp.entities_serialization)
        log.write(POST_COMBAT_COMMANDS_MENU)

    ########################################################################################################################
    @on(Input.Submitted, "#combat-post-combat-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        self._dispatch_command(raw)

    ########################################################################################################################
    @work
    async def _dispatch_command(self, raw: str) -> None:
        """指令分发：1-4、6 为查阅型（GET）指令，每次都重新 GET 场景花名册，避免使用过期数据；
        指令 5（退出地下城）会改变状态，单独处理。"""
        log = self.query_one(RichLog)

        if raw not in ("1", "2", "3", "4", "5", "6"):
            log.write("[red]无效指令，请输入 1-6[/]")
            return

        if raw == "5":
            self._do_exit_dungeon()
            return

        if raw == "6":
            self.app.push_screen(CombatLootViewScreen())
            return

        try:
            _, _, actor_name = resolve_identity(self.game_client)
            room_resp = await get_dungeon_room(self.game_client)
            room = room_resp.room
            assert isinstance(
                room, CombatRoom
            ), f"当前房间不是战斗房间：type={room.type}"
            assert room.type == "combat"
            combat = room.combat
        except Exception as e:
            logger.error(
                f"CombatPostCombatScreen._dispatch_command: 校验战斗状态失败 error={e}"
            )
            log.write(f"[bold red]❌ 校验战斗状态失败：{e}[/]")
            return

        if raw == "4":
            self.app.push_screen(CombatRoundHistoryScreen(combat.rounds))
            return

        try:
            stages_resp = await get_stages_state(self.game_client)
            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert (
                stage_name is not None
            ), f"未能在场景映射中找到玩家角色所在场景：actor={actor_name}"
            participant_names = list(stages_resp.mapping[stage_name])
        except Exception as e:
            logger.error(
                f"CombatPostCombatScreen._dispatch_command: 获取场景花名册失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取场景花名册失败：{e}[/]")
            return

        if raw == "1":
            self.app.push_screen(CombatDeckViewScreen(participant_names))
        elif raw == "2":
            self.app.push_screen(CombatInventoryViewScreen())
        elif raw == "3":
            candidates: List[Tuple[str, str]] = [(stage_name, "场景")]
            candidates.extend((name, "角色") for name in participant_names)
            self.app.push_screen(CombatEntityInspectScreen(candidates))

    ########################################################################################################################
    @work
    async def _do_exit_dungeon(self) -> None:
        """退出地下城，返回家园。

        - mock 模式（session 为 None，即通过 `--dev-screen combat-post-combat` 跳过登录
          直接进入本页调试）：不存在真实后端会话可退出，直接退出应用，与
          `action_go_back` 中的判断保持一致。
        - 正式流程：调用 /api/dungeon/exit/v1/（服务端 exit_dungeon）退出地下城，
          成功后 switch_screen 到 HomeScreen（与 new_game.py 创建游戏成功后进入
          HomeScreen 的方式一致）。
        """
        log = self.query_one(RichLog)

        if is_mock_mode(self.game_client):
            logger.info(
                "CombatPostCombatScreen._do_exit_dungeon: mock 模式，直接退出应用"
            )
            log.write("[dim]mock 模式：无真实会话可退出地下城，直接退出应用[/]")
            self.app.exit()
            return

        inp = self.query_one(Input)
        inp.disabled = True
        log.write("[dim]▶ 正在退出地下城...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_exit(user_name, game_name)
        except Exception as e:
            logger.error(f"CombatPostCombatScreen._do_exit_dungeon: 退出失败 error={e}")
            log.write(f"[bold red]❌ 退出地下城失败：{e}[/]")
            inp.disabled = False
            inp.focus()
            return

        log.write(f"[bold green]✅ {resp.message}[/]")
        logger.info(
            f"CombatPostCombatScreen._do_exit_dungeon: 退出成功 user_name={user_name} "
            f"game_name={game_name} message={resp.message}"
        )

        self.app.switch_screen(HomeScreen())
