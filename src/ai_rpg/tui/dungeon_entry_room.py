"""入口房间 Screen"""

from typing import List, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import EntryRoom
from .base import BaseGameScreen
from .combat_common import (
    find_stage_of_actor,
    render_stage_actors,
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
    dungeon_entry_init,
    dungeon_advance_stage,
    watch_task_until_done,
)

BASE_INFO_HEADER = """\
[bold cyan]── 入口房间 ──────────────────────────────────────[/]

[dim]非战斗叙事场景，用于副本开场铺垫与牌库生成。[/]
"""

COMMANDS_MENU = """\
[bold yellow]── 可用操作 ─────────────────────────────────[/]
  [bold green]1[/]  创建牌组
  [bold green]2[/]  查阅牌组（我方）
  [bold green]3[/]  查阅我方背包
  [bold green]4[/]  查阅指定实体信息（场景 / 角色）
  [bold green]5[/]  进入下一关
"""


@final
class DungeonEntryRoomScreen(BaseGameScreen):
    """入口房间 Screen：进入即自动加载场景描述与角色属性，提供牌组生成等命令。"""

    CSS = """
    DungeonEntryRoomScreen {
        align: center middle;
    }

    #entry-room-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #entry-room-input-row {
        height: 3;
        dock: bottom;
    }

    #entry-room-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #entry-room-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "app.quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(id="entry-room-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="entry-room-input-row"):
            yield Static("> ", id="entry-room-prompt")
            yield Input(placeholder="输入指令编号...", id="entry-room-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(BASE_INFO_HEADER)
        self._load_base_info()
        self.query_one(Input).focus()

    ########################################################################################################################
    @work
    async def _load_base_info(self) -> None:
        """加载并渲染入口房间场景描述 + 场景内角色有效属性。"""
        log = self.query_one(RichLog)
        logger.info("EntryRoomScreen._load_base_info: 开始加载")

        try:
            _, _, actor_name = resolve_identity(self.game_client)

            room_resp = await get_dungeon_room(self.game_client)
            stages_resp = await get_stages_state(self.game_client)

            room = room_resp.room
            assert isinstance(
                room, EntryRoom
            ), f"当前房间不是入口房间：type={room.type}"

            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert (
                stage_name is not None
            ), f"未能在场景映射中找到玩家角色所在场景：actor={actor_name}"
            actor_names = stages_resp.mapping[stage_name]
            entity_names = [stage_name, *actor_names]

            entities_resp = await get_entities_details(self.game_client, entity_names)

        except Exception as e:
            logger.error(f"EntryRoomScreen._load_base_info: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载入口房间信息失败：{e}[/]")
            return

        # 渲染场景名 + 场景描述
        log.write(
            f"[bold yellow]── 场景：{stage_name} ─────────────────────────────[/]"
        )
        log.write(f"  {room.stage.profile}")
        log.write("")

        # 渲染场景内角色有效属性
        render_stage_actors(log, stage_name, entities_resp.entities)

        # 始终显示命令菜单（入口房间无战斗状态机）
        log.write(COMMANDS_MENU)

    ########################################################################################################################
    @on(Input.Submitted, "#entry-room-input")
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
        log = self.query_one(RichLog)

        if raw not in ("1", "2", "3", "4", "5"):
            log.write("[red]无效指令，请输入 1-5[/]")
            return

        try:
            _, _, actor_name = resolve_identity(self.game_client)
            room_resp = await get_dungeon_room(self.game_client)
            room = room_resp.room
            assert isinstance(
                room, EntryRoom
            ), f"当前房间不是入口房间：type={room.type}"
        except Exception as e:
            logger.error(
                f"EntryRoomScreen._dispatch_command: 校验房间状态失败 error={e}"
            )
            log.write(f"[bold red]❌ 校验房间状态失败：{e}[/]")
            return

        # 命令 1：创建牌组（后台任务），无需场景花名册
        if raw == "1":
            self._init_entry_room()
            return

        # 命令 2/3/4 需要场景花名册
        try:
            stages_resp = await get_stages_state(self.game_client)
            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert (
                stage_name is not None
            ), f"未能在场景映射中找到玩家角色所在场景：actor={actor_name}"
            participant_names = list(stages_resp.mapping[stage_name])
        except Exception as e:
            logger.error(
                f"EntryRoomScreen._dispatch_command: 获取场景花名册失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取场景花名册失败：{e}[/]")
            return

        if raw == "2":
            # 仅我方（party），过滤出 NPC / Player 角色
            party_names = [name for name in participant_names if name != stage_name]
            self.app.push_screen(CombatDeckViewScreen(party_names))
        elif raw == "3":
            self.app.push_screen(CombatInventoryViewScreen())
        elif raw == "4":
            candidates: List[Tuple[str, str]] = [(stage_name, "场景")]
            candidates.extend((name, "角色") for name in participant_names)
            self.app.push_screen(CombatEntityInspectScreen(candidates))
        elif raw == "5":
            self._advance_stage()

    ########################################################################################################################
    @work
    async def _init_entry_room(self) -> None:
        """触发入口房间初始化（创建牌组）并等待完成。"""
        log = self.query_one(RichLog)
        logger.info("EntryRoomScreen._init_entry_room: 触发入口房间初始化")
        log.write("[dim]正在触发入口房间初始化（叙事 + 牌库生成），请稍候...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_entry_init(user_name, game_name)
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            record = await watch_task_until_done(resp.task_id)
            log.write(f"[bold green]✅ 入口房间初始化完成：{record.status}[/]")
            log.write("[dim]牌组已生成，可使用命令 2 查阅牌组。[/]")
        except TaskFailedError as e:
            logger.error(f"EntryRoomScreen._init_entry_room: 任务失败 error={e}")
            log.write(f"[bold red]❌ 入口房间初始化失败：{e}[/]")
        except Exception as e:
            logger.error(f"EntryRoomScreen._init_entry_room: 请求失败 error={e}")
            log.write(f"[bold red]❌ 请求失败：{e}[/]")

    ########################################################################################################################
    @work
    async def _advance_stage(self) -> None:
        """进入下一关。先校验是否存在下一房间，再调用推进接口，最后回到副本总览。"""
        log = self.query_one(RichLog)
        logger.info("EntryRoomScreen._advance_stage: 进入下一关")
        log.write("[dim]正在进入下一关...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)

            # 先查询副本状态，确认存在下一房间
            dungeon_resp = await get_dungeon_state(self.game_client)
            dungeon = dungeon_resp.dungeon
            next_index = dungeon.current_room_index + 1
            if next_index >= len(dungeon.rooms):
                log.write("[bold red]❌ 已是最后一关，无法继续推进。[/]")
                return

            # 调用推进接口
            resp = await dungeon_advance_stage(user_name, game_name)
            log.write(f"[bold green]✅ {resp.message}[/]")
            log.write("[dim]返回副本总览...[/]")

            # 回到副本房间路由，让其重新根据当前房间类型分发到对应 Screen
            # 注：延迟导入避免循环引用（dungeon_room_router_room → entry_room）
            from .dungeon_room_router_room import DungeonRoomRouterRoom

            self.app.switch_screen(DungeonRoomRouterRoom())
        except Exception as e:
            logger.error(f"EntryRoomScreen._advance_stage: 推进失败 error={e}")
            log.write(f"[bold red]❌ 进入下一关失败：{e}[/]")
