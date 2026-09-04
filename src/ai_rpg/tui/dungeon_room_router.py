"""副本房间路由：按当前房间类型直接 switch_screen 到对应页面。"""

from loguru import logger

from ..models import CombatRoom, OpeningRoom
from .app import GameClient
from .server_client import fetch_dungeon_state


async def route_to_current_room(app: GameClient) -> None:
    """查询当前副本房间，按类型直接 switch_screen 到对应页面。

    调用方需已持有有效 session；session 为 None（dev-screen）时不做任何事。
    """
    session = app.session
    if session is None:
        logger.warning("route_to_current_room: session 为空，无法路由")
        return

    try:
        resp = await fetch_dungeon_state(session.user_name, session.game_name)
    except Exception as e:
        logger.error(f"route_to_current_room: 查询副本状态失败 error={e}")
        return

    room = resp.dungeon.current_room
    if room is None:
        logger.warning("route_to_current_room: 当前没有有效房间")
        return

    if isinstance(room, CombatRoom):
        # 延迟导入，避免在模块顶层形成 import 环
        from .combat_init import CombatInitScreen

        logger.info(f"route_to_current_room: 进入战斗房间 stage={room.stage.name}")
        app.switch_screen(CombatInitScreen())
    elif isinstance(room, OpeningRoom):
        from .dungeon_opening_room import DungeonOpeningRoomScreen

        logger.info(f"route_to_current_room: 进入开场房间 stage={room.stage.name}")
        app.switch_screen(DungeonOpeningRoomScreen())
    else:
        logger.warning(f"route_to_current_room: 未知房间类型 type={room.type}")
