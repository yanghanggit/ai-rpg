"""副本房间路由 Screen（DungeonRoomRouterRoom）"""

from typing import final

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.widgets import Static
from .base import BaseGameScreen
from .server_client import fetch_dungeon_state
from .combat_room import CombatRoomScreen
from .dungeon_entry_room import DungeonEntryRoomScreen
from ..models import CombatRoom, EntryRoom, DungeonRoom


@final
class DungeonRoomRouterRoom(BaseGameScreen):
    """副本房间路由 Screen：查询当前房间类型后 switch 到对应的具体房间 Screen。"""

    def compose(self) -> ComposeResult:
        yield Static(
            "[dim]正在进入房间...[/]", id="dungeon-room-router-room-placeholder"
        )

    def on_mount(self) -> None:
        self._route()

    @work
    async def _route(self) -> None:
        """查询当前副本状态，取 current_room_index 对应的房间，根据其
        type 判别字段分发到具体房间 Screen。"""
        assert self.game_client.session is not None
        user_name = self.game_client.session.user_name
        game_name = self.game_client.session.game_name

        logger.info(f"DungeonRoomRouterRoom._route: user={user_name} game={game_name}")

        try:
            resp = await fetch_dungeon_state(user_name, game_name)
            room = resp.dungeon.current_room
        except Exception as e:
            logger.error(f"DungeonRoomRouterRoom._route: 查询副本状态失败 error={e}")
            self.query_one(Static).update(f"[bold red]❌ 查询副本状态失败：{e}[/]")
            return

        if room is None:
            logger.warning(
                "DungeonRoomRouterRoom._route: current_room_index 无效，当前无有效房间"
            )
            self.query_one(Static).update("[bold red]❌ 当前没有有效的房间[/]")
            return

        # 根据房间类型路由到具体房间 Screen
        if isinstance(room, CombatRoom):
            logger.info("DungeonRoomRouterRoom._route: 路由至 CombatRoomScreen")
            self.app.switch_screen(CombatRoomScreen())
        elif isinstance(room, EntryRoom):
            logger.info("DungeonRoomRouterRoom._route: 路由至 EntryRoomScreen")
            self.app.switch_screen(DungeonEntryRoomScreen())
        elif isinstance(room, DungeonRoom):
            logger.info(f"DungeonRoomRouterRoom._route: 未知基类房间 type={room.type}")
            self.query_one(Static).update(
                f"[bold cyan]📍 {room.stage.name}[/]\n\n"
                f"{room.stage.profile}\n\n"
                f"[dim]输入 'next' 前进到下一关[/]"
            )
        else:
            logger.warning(
                f"DungeonRoomRouterRoom._route: 未知房间类型 type={room.type}"
            )
            self.query_one(Static).update(f"[bold red]❌ 未知房间类型：{room.type}[/]")
