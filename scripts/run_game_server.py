import asyncio
import contextlib
import os
import sys
from typing import Any, AsyncIterator, Dict

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
# 将 scripts 目录添加到模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from loguru import logger
from config import GAME_SERVER_PORT
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from ai_rpg.pgsql import procrastinate_app
from ai_rpg.services.dungeon_lifecycle_api import (
    dungeon_lifecycle_api_router,
)
from ai_rpg.services.dungeon_combat_api import (
    dungeon_combat_api_router,
)
from ai_rpg.services.dungeon_opening_api import (
    dungeon_opening_api_router,
)
from ai_rpg.services.home_api import home_api_router
from ai_rpg.services.login import login_api_router
from ai_rpg.services.new_game import new_game_api_router
from datetime import datetime
from ai_rpg.services.entity_details import (
    entity_details_api_router,
)
from ai_rpg.services.dungeon_state import dungeon_state_api_router
from ai_rpg.services.stages_state import stages_state_api_router
from ai_rpg.services.background_tasks import background_tasks_api_router
from ai_rpg.services.player_session import player_session_api_router
from config import LOGS_DIR
from ai_rpg.replicate import (
    GENERATED_IMAGES_OUTPUT_DIR,
    GENERATED_IMAGES_URL_PREFIX,
)


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


@app.get(path="/")
async def get_api_info(request: Request) -> Dict[str, Any]:
    """API 根路由接口"""
    from fastapi.routing import APIRoute

    base_url = str(request.base_url)
    logger.info(f"获取API路由信息: {base_url}")

    # 收集所有已注册的路由信息
    routes_info = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes_info.append(
                {
                    "path": route.path,
                    "name": route.name,
                    "methods": list(route.methods),
                    "tags": route.tags if route.tags else [],
                }
            )

    return {
        "service": "AI RPG DBG Game Server",
        "base_url": base_url,
        "description": "AI RPG DBG Game Server API Root Endpoint",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "0.0.1",
        "routes": routes_info,
    }


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

############################################################################################################
# 挂载静态文件服务
app.mount(
    GENERATED_IMAGES_URL_PREFIX,
    StaticFiles(directory=str(GENERATED_IMAGES_OUTPUT_DIR)),
    name=GENERATED_IMAGES_URL_PREFIX.lstrip("/"),
)

# 注册各个 API 路由
app.include_router(router=player_session_api_router)
app.include_router(router=entity_details_api_router)
app.include_router(router=stages_state_api_router)
app.include_router(router=dungeon_state_api_router)
app.include_router(router=background_tasks_api_router)
app.include_router(router=login_api_router)
app.include_router(router=new_game_api_router)
app.include_router(router=home_api_router)
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
