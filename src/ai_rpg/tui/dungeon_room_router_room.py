"""地下城房间路由 Screen（DungeonRoomRouterRoom）"""

from typing import final

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.widgets import Static
from .base import BaseGameScreen
from .server_client import fetch_dungeon_state
from .combat_room import CombatRoomScreen
from ..models import CombatRoom


@final
class DungeonRoomRouterRoom(BaseGameScreen):
    """地下城房间路由 Screen：查询当前房间类型后 switch 到对应的具体房间 Screen。"""

    def compose(self) -> ComposeResult:
        yield Static(
            "[dim]正在进入房间...[/]", id="dungeon-room-router-room-placeholder"
        )

    def on_mount(self) -> None:
        self._route()

    @work
    async def _route(self) -> None:
        """查询当前地下城状态，取 current_room_index 对应的房间，根据其
        room_type 判别字段分发到具体房间 Screen。"""
        assert self.game_client.session is not None
        user_name = self.game_client.session.user_name
        game_name = self.game_client.session.game_name

        logger.info(f"DungeonRoomRouterRoom._route: user={user_name} game={game_name}")

        try:
            resp = await fetch_dungeon_state(user_name, game_name)
            room = resp.dungeon.current_room
        except Exception as e:
            logger.error(f"DungeonRoomRouterRoom._route: 查询地下城状态失败 error={e}")
            self.query_one(Static).update(f"[bold red]❌ 查询地下城状态失败：{e}[/]")
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
        else:
            logger.warning(
                f"DungeonRoomRouterRoom._route: 未知房间类型 room_type={room.room_type}"
            )
            self.query_one(Static).update(
                f"[bold red]❌ 未知房间类型：{room.room_type}[/]"
            )
