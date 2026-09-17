import asyncio
import contextlib
import os
import sys
from typing import AsyncIterator

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
# 将 scripts 目录添加到模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from datetime import datetime

from config import GAME_SERVER_PORT, LOGS_DIR
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.types import Scope

from ai_rpg.models import (
    ASSETS_DIR,
    ASSETS_URL_PREFIX,
    ApiRouteInfo,
    ServerInfoResponse,
)
from ai_rpg.pgsql import procrastinate_app
from ai_rpg.services.compact_api import compact_api_router
from ai_rpg.services.dungeon_combat_api import (
    dungeon_combat_api_router,
)
from ai_rpg.services.dungeon_lifecycle_api import (
    dungeon_lifecycle_api_router,
)
from ai_rpg.services.dungeon_opening_api import (
    dungeon_opening_api_router,
)
from ai_rpg.services.dungeon_state import dungeon_state_api_router
from ai_rpg.services.entity_details import (
    entity_details_api_router,
)
from ai_rpg.services.home_api import home_api_router
from ai_rpg.services.login import login_api_router
from ai_rpg.services.new_game import new_game_api_router
from ai_rpg.services.player_session import player_session_api_router
from ai_rpg.services.stages_state import stages_state_api_router
from ai_rpg.services.tasks_api import tasks_api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """在 FastAPI 生命周期内打开 Procrastinate 并嵌入运行 worker（与 GameServer 单例同进程/同事件循环）"""
    async with procrastinate_app.open_async():
        worker_task = asyncio.create_task(
            procrastinate_app.run_worker_async(install_signal_handlers=False)
        )
        try:
            yield
        finally:
            worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(worker_task, timeout=10)


app = FastAPI(lifespan=lifespan)


@app.get(path="/", response_model=ServerInfoResponse)
async def get_api_info(request: Request) -> ServerInfoResponse:
    """API 根路由接口"""
    from fastapi.routing import APIRoute

    base_url = str(request.base_url)
    logger.info(f"获取API路由信息: {base_url}")

    # 收集所有已注册的路由信息
    # FastAPI 把 APIRoute.tags 标注为 list[str | Enum]；本项目只用字符串标签，
    # 这里统一成 str 以匹配 ServerInfoResponse 的字段类型。
    routes_info: list[ApiRouteInfo] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes_info.append(
                ApiRouteInfo(
                    path=route.path,
                    name=route.name,
                    methods=list(route.methods),
                    tags=[str(tag) for tag in route.tags] if route.tags else [],
                )
            )

    return ServerInfoResponse(
        service="AI RPG DBG Game Server",
        base_url=base_url,
        assets_url_prefix=ASSETS_URL_PREFIX,
        description="AI RPG DBG Game Server API Root Endpoint",
        status="healthy",
        timestamp=datetime.now(),
        version="0.0.1",
        routes=routes_info,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


############################################################################################################
# 挂载静态文件服务
class AssetStaticFiles(StaticFiles):
    """资源静态服务。

    资源文件名内容寻址（``<UTC时间戳>_<uuid>``，生成后永不改写），因此可安全地
    声明为不可变资源，让浏览器/CDN 长期缓存、连条件请求（304）都不再发起。
    """

    _CACHE_CONTROL = "public, max-age=31536000, immutable"

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["cache-control"] = self._CACHE_CONTROL
        return response


app.mount(
    ASSETS_URL_PREFIX,
    AssetStaticFiles(directory=str(ASSETS_DIR)),
    name=ASSETS_URL_PREFIX.lstrip("/"),
)

# 注册各个 API 路由
app.include_router(router=player_session_api_router)
app.include_router(router=entity_details_api_router)
app.include_router(router=stages_state_api_router)
app.include_router(router=dungeon_state_api_router)
app.include_router(router=tasks_api_router)
app.include_router(router=login_api_router)
app.include_router(router=new_game_api_router)
app.include_router(router=home_api_router)
app.include_router(router=compact_api_router)
app.include_router(router=dungeon_lifecycle_api_router)
app.include_router(router=dungeon_combat_api_router)
app.include_router(router=dungeon_opening_api_router)


def main() -> None:

    import datetime

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_game_server_{_timestamp}.log"
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(_log_file, level="DEBUG")
    logger.info(f"日志配置: 级别=DEBUG, 文件路径={_log_file}")

    logger.info(f"启动游戏服务器，端口: {GAME_SERVER_PORT}")

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=GAME_SERVER_PORT,
    )


if __name__ == "__main__":
    main()
