"""房间领域异常到 HTTP 状态码的统一映射。"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..game.game_server import (
    RoomAlreadyExistsError,
    RoomNotFoundError,
)
from ..game.player_room import RoomClosedError
from .game_state_errors import GameStateError
from .task_dispatch import RoomBusyError


###############################################################################################################################################
def register_room_error_handlers(app: FastAPI) -> None:
    """注册房间相关的领域异常处理器。"""

    @app.exception_handler(RoomNotFoundError)
    async def _room_not_found(request: Request, exc: RoomNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "没有房间，请先登录"})

    @app.exception_handler(RoomClosedError)
    async def _room_closed(request: Request, exc: RoomClosedError) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"detail": "房间已关闭，请重新登录"}
        )

    @app.exception_handler(RoomAlreadyExistsError)
    async def _room_exists(
        request: Request, exc: RoomAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "房间已存在"})

    @app.exception_handler(RoomBusyError)
    async def _room_busy(request: Request, exc: RoomBusyError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "该房间已有任务在进行中，请稍后重试"},
        )

    @app.exception_handler(GameStateError)
    async def _game_state_error(request: Request, exc: GameStateError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


###############################################################################################################################################
