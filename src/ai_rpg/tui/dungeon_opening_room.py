"""开场房间 Screen

布局（从上到下，固定区域 + 可追加区域）：
  1) title        —— 固定标题
  2) base 信息区   —— 固定显示位置，展示场景环境描述（StageDescriptionComponent.narrative），可被重置
  3) 命令列表区    —— 固定显示位置
  4) 输出信息区    —— 可追加日志（RichLog）
"""

from typing import List, Optional, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import (
    EntitiesDetailsResponse,
    OpeningRoom,
    StageDescriptionComponent,
)
from .base import BaseGameScreen
from .combat_card_pool_view import CombatCardPoolViewScreen
from .combat_common import (
    find_component_data,
    find_stage_of_actor,
)
from .combat_data_access import (
    get_dungeon_room,
    get_dungeon_state,
    get_entities_details,
    get_stages_state,
    resolve_identity,
)
from .combat_deck_view import CombatDeckViewScreen
from .combat_entity_inspect import CombatEntityInspectScreen
from .combat_inventory_view import CombatInventoryViewScreen
from .server_client import (
    TaskFailedError,
    dungeon_advance_stage,
    dungeon_opening_generate_card_pool,
    dungeon_opening_init,
    watch_task_until_done,
)

TITLE_TEXT = """\
[bold cyan]── 开场房间 ──────────────────────────────────────[/]

[dim]非战斗叙事场景，用于副本开场铺垫、牌库初始化与卡池生成。[/]
"""

BASE_INFO_EMPTY = "[dim]（暂无场景描述）[/]"

COMMANDS_MENU = """\
[bold yellow]── 可用操作 ─────────────────────────────────[/]
  [bold green]0[/]  刷新本页
  [bold green]1[/]  初始化开场房间（叙事 + 牌库）
  [bold green]2[/]  生成卡池
  [bold green]3[/]  查阅牌组（我方）
  [bold green]4[/]  查阅卡池 / 挑卡（我方）
  [bold green]5[/]  查阅我方背包
  [bold green]6[/]  查阅指定实体信息（场景 / 角色）
  [bold green]7[/]  进入下一关
"""


@final
class DungeonOpeningRoomScreen(BaseGameScreen):
    """开场房间 Screen：title / base 信息区 / 命令列表区固定显示，输出信息区可追加。"""

    CSS = """
    DungeonOpeningRoomScreen {
        align-horizontal: center;
    }

    #opening-room-title {
        width: 100%;
        padding: 0 1;
    }

    #opening-room-base-info {
        width: 100%;
        padding: 0 1;
        border: solid $primary;
    }

    #opening-room-commands {
        width: 100%;
        padding: 0 1;
    }

    #opening-room-output {
        width: 100%;
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }

    #opening-room-input-row {
        height: 3;
        dock: bottom;
    }

    #opening-room-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #opening-room-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "app.quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(TITLE_TEXT, id="opening-room-title")
        yield Static(BASE_INFO_EMPTY, id="opening-room-base-info")
        yield Static(COMMANDS_MENU, id="opening-room-commands")
        yield RichLog(id="opening-room-output", highlight=True, markup=True, wrap=True)
        with Horizontal(id="opening-room-input-row"):
            yield Static("> ", id="opening-room-prompt")
            yield Input(placeholder="输入指令编号...", id="opening-room-input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    ########################################################################################################################
    def _output(self) -> RichLog:
        """返回输出信息区（可追加日志的 RichLog）。"""
        return self.query_one("#opening-room-output", RichLog)

    ########################################################################################################################
    def _set_base_info(self, text: str) -> None:
        """重置 base 信息区显示内容。"""
        self.query_one("#opening-room-base-info", Static).update(text)

    ########################################################################################################################
    @staticmethod
    def _extract_stage_narrative(
        entities_resp: EntitiesDetailsResponse, stage_name: str
    ) -> Optional[str]:
        """从实体详情响应中提取场景实体的 StageDescriptionComponent.narrative。"""
        for entity in entities_resp.entities:
            if entity.name != stage_name:
                continue
            data = find_component_data(entity, StageDescriptionComponent.__name__)
            if data is not None:
                return StageDescriptionComponent(**data).narrative
        return None

    ########################################################################################################################
    async def _refresh_base_info(self) -> None:
        """刷新 base 信息区：重新拉取场景 narrative 并重置显示。"""
        output = self._output()
        logger.info("OpeningRoomScreen._refresh_base_info: 刷新基础信息")
        try:
            _, _, actor_name = resolve_identity(self.game_client)
            stages_resp = await get_stages_state(self.game_client)
            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert stage_name is not None, "无法确定玩家所在场景"

            entities_resp = await get_entities_details(self.game_client, [stage_name])
            narrative = self._extract_stage_narrative(entities_resp, stage_name)

            description = (
                f"  {narrative}" if narrative else "  [dim]（场景环境描述未生成）[/]"
            )
            self._set_base_info(
                f"[bold yellow]── 场景：{stage_name} ─────────────────────────────[/]\n\n"
                f"{description}"
            )
            output.write("[dim]已刷新基础信息。[/]")
        except Exception as e:
            logger.error(f"OpeningRoomScreen._refresh_base_info: 刷新失败 error={e}")
            output.write(f"[bold red]❌ 刷新基础信息失败：{e}[/]")

    ########################################################################################################################
    @on(Input.Submitted, "#opening-room-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        self._dispatch_command(raw)

    ########################################################################################################################
    @work
    async def _dispatch_command(self, raw: str) -> None:
        """指令分发。每次都重新 GET 校验房间类型与场景花名册，避免使用过期快照。"""
        output = self._output()

        if raw not in ("0", "1", "2", "3", "4", "5", "6", "7"):
            output.write("[red]无效指令，请输入 0-7[/]")
            return

        # 命令 0：刷新本页（重置 base 信息区）
        if raw == "0":
            await self._refresh_base_info()
            return

        try:
            _, _, actor_name = resolve_identity(self.game_client)
            room_resp = await get_dungeon_room(self.game_client)
            room = room_resp.room
            assert isinstance(
                room, OpeningRoom
            ), f"当前房间不是开场房间：type={room.type}"
        except Exception as e:
            logger.error(
                f"OpeningRoomScreen._dispatch_command: 校验房间状态失败 error={e}"
            )
            output.write(f"[bold red]❌ 校验房间状态失败：{e}[/]")
            return

        # 命令 1：初始化开场房间（叙事 + 牌库），后台任务，无需场景花名册
        if raw == "1":
            self._init_opening_room()
            return

        # 命令 2：生成卡池（后台任务），无需场景花名册
        if raw == "2":
            self._generate_card_pool()
            return

        # 命令 3/4/5/6 需要场景花名册
        try:
            stages_resp = await get_stages_state(self.game_client)
            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert (
                stage_name is not None
            ), f"未能在场景映射中找到玩家角色所在场景：actor={actor_name}"
            participant_names = list(stages_resp.mapping[stage_name])
        except Exception as e:
            logger.error(
                f"OpeningRoomScreen._dispatch_command: 获取场景花名册失败 error={e}"
            )
            output.write(f"[bold red]❌ 获取场景花名册失败：{e}[/]")
            return

        if raw == "3":
            # 仅我方（party），过滤出 NPC / Player 角色
            party_names = [name for name in participant_names if name != stage_name]
            self.app.push_screen(CombatDeckViewScreen(party_names))
        elif raw == "4":
            # 仅我方（party），过滤出 NPC / Player 角色
            party_names = [name for name in participant_names if name != stage_name]
            self.app.push_screen(CombatCardPoolViewScreen(party_names))
        elif raw == "5":
            self.app.push_screen(CombatInventoryViewScreen())
        elif raw == "6":
            candidates: List[Tuple[str, str]] = [(stage_name, "场景")]
            candidates.extend((name, "角色") for name in participant_names)
            self.app.push_screen(CombatEntityInspectScreen(candidates))
        elif raw == "7":
            self._advance_stage()

    ########################################################################################################################
    @work
    async def _init_opening_room(self) -> None:
        """触发开场房间初始化（叙事 + 牌库）并等待完成。"""
        output = self._output()
        logger.info("OpeningRoomScreen._init_opening_room: 触发开场房间初始化")
        output.write("[dim]正在触发开场房间初始化（叙事 + 牌库），请稍候...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_opening_init(user_name, game_name)
            output.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            record = await watch_task_until_done(resp.task_id)
            output.write(f"[bold green]✅ 开场房间初始化完成：{record.status}[/]")
            output.write("[dim]牌组已生成，可使用命令 3 查阅牌组，命令 2 生成卡池。[/]")
            await self._refresh_base_info()
        except TaskFailedError as e:
            logger.error(f"OpeningRoomScreen._init_opening_room: 任务失败 error={e}")
            output.write(f"[bold red]❌ 开场房间初始化失败：{e}[/]")
        except Exception as e:
            logger.error(f"OpeningRoomScreen._init_opening_room: 请求失败 error={e}")
            output.write(f"[bold red]❌ 请求失败：{e}[/]")

    ########################################################################################################################
    @work
    async def _generate_card_pool(self) -> None:
        """触发卡池生成（外部显式触发 GenerateCardPoolAction）并等待完成。"""
        output = self._output()
        logger.info("OpeningRoomScreen._generate_card_pool: 触发卡池生成")
        output.write("[dim]正在生成卡池，请稍候...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_opening_generate_card_pool(user_name, game_name)
            output.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            record = await watch_task_until_done(resp.task_id)
            output.write(f"[bold green]✅ 卡池生成完成：{record.status}[/]")
            output.write(
                "[dim]卡池已生成，可使用命令 4 查阅卡池，命令 7 进入下一关。[/]"
            )
        except TaskFailedError as e:
            logger.error(f"OpeningRoomScreen._generate_card_pool: 任务失败 error={e}")
            output.write(f"[bold red]❌ 卡池生成失败：{e}[/]")
        except Exception as e:
            logger.error(f"OpeningRoomScreen._generate_card_pool: 请求失败 error={e}")
            output.write(f"[bold red]❌ 请求失败：{e}[/]")

    ########################################################################################################################
    @work
    async def _advance_stage(self) -> None:
        """进入下一关。先校验是否存在下一房间，再调用推进接口，最后回到副本总览。"""
        output = self._output()
        logger.info("OpeningRoomScreen._advance_stage: 进入下一关")
        output.write("[dim]正在进入下一关...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)

            # 先查询副本状态，确认存在下一房间
            dungeon_resp = await get_dungeon_state(self.game_client)
            dungeon = dungeon_resp.dungeon
            next_index = dungeon.current_room_index + 1
            if next_index >= len(dungeon.rooms):
                output.write("[bold red]❌ 已是最后一关，无法继续推进。[/]")
                return

            # 调用推进接口
            resp = await dungeon_advance_stage(user_name, game_name)
            output.write(f"[bold green]✅ {resp.message}[/]")
            output.write("[dim]返回副本总览...[/]")

            # 回到副本房间路由，让其重新根据当前房间类型分发到对应 Screen
            # 注：延迟导入避免循环引用（dungeon_room_router_room → opening_room）
            from .dungeon_room_router_room import DungeonRoomRouterRoom

            self.app.switch_screen(DungeonRoomRouterRoom())
        except Exception as e:
            logger.error(f"OpeningRoomScreen._advance_stage: 推进失败 error={e}")
            output.write(f"[bold red]❌ 进入下一关失败：{e}[/]")
