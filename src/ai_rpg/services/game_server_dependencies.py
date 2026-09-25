"""游戏服务器依赖注入模块。

HTTP 请求从 ``app.state`` 获取进程级 GameServer；后台任务见 ``game_server_runtime``。
"""

from typing import Annotated

from fastapi import Depends, Request

from ..game.game_server import GameServer


###############################################################################################################################################
def get_game_server(request: Request) -> GameServer:
    """FastAPI 依赖：从 ``app.state`` 获取进程级 GameServer。"""
    game_server: GameServer = request.app.state.game_server
    return game_server


###############################################################################################################################################
# 类型注解别名，用于 FastAPI 依赖注入
CurrentGameServer = Annotated[GameServer, Depends(get_game_server)]
