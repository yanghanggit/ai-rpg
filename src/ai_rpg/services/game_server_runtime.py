"""进程级 GameServer 的运行时访问。

HTTP 路径用 ``game_server_dependencies.CurrentGameServer``（Request 上下文）；
无 Request 的运行时上下文（当前为后台任务）用 ``get_runtime_game_server``。
实例由应用启动时的 ``lifespan`` 显式绑定。
"""

from typing import Optional

from ..game.game_server import GameServer

_runtime_game_server: Optional[GameServer] = None


###############################################################################################################################################
def bind_runtime_game_server(game_server: GameServer) -> None:
    """在应用启动时绑定进程级 GameServer（供非请求上下文使用）。"""
    global _runtime_game_server
    _runtime_game_server = game_server


###############################################################################################################################################
def get_runtime_game_server() -> GameServer:
    """获取进程级 GameServer。"""
    if _runtime_game_server is None:
        raise RuntimeError("GameServer 尚未初始化")
    return _runtime_game_server
