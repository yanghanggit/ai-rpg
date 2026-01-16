"""游戏服务器依赖注入模块

提供 FastAPI 依赖注入的游戏服务器单例实例。
"""

from typing import Annotated, Optional
from fastapi import Depends
from ..game.game_server import GameServer


_game_server_instance: Optional[GameServer] = None


###############################################################################################################################################
def get_game_server() -> GameServer:
    """获取游戏服务器单例实例

    Returns:
        GameServer: 游戏服务器实例
    """
    global _game_server_instance
    if _game_server_instance is None:
        _game_server_instance = GameServer()
    return _game_server_instance


###############################################################################################################################################
# 类型注解别名，用于 FastAPI 依赖注入
CurrentGameServer = Annotated[GameServer, Depends(get_game_server)]
