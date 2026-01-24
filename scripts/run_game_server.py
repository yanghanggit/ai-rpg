import os
from pathlib import Path
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Final

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from loguru import logger
from ai_rpg.configuration import (
    server_configuration,
)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from ai_rpg.services.dungeon_gameplay import (
    dungeon_gameplay_api_router,
)
from ai_rpg.services.home_gameplay import home_gameplay_api_router
from ai_rpg.services.login import login_api_router
from ai_rpg.services.start import start_api_router
from datetime import datetime
from ai_rpg.services.entity_details import (
    entity_details_api_router,
)
from ai_rpg.services.dungeon_state import dungeon_state_api_router
from ai_rpg.services.stages_state import stages_state_api_router
from ai_rpg.services.background_tasks import background_tasks_api_router
from ai_rpg.chat_client.client import ChatClient
from ai_rpg.services.player_session import player_session_api_router
from ai_rpg.game.config import setup_logger

# 服务器配置文件路径
_server_setting_path: Final[Path] = Path("server_configuration.json")
assert _server_setting_path.exists(), f"{_server_setting_path} must exist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI 应用生命周期管理

    处理应用启动和关闭时的初始化和清理操作。
    """
    # 启动时的初始化操作
    logger.info("🚀 TCG游戏服务器启动中...")

    # 在这里添加启动时需要执行的初始化操作
    try:

        logger.info(
            f"✅ 服务器配置已加载，端口: {server_configuration.game_server_port}"
        )

        # 可以在这里添加其他初始化操作，比如：
        # - 数据库连接初始化
        # - 缓存系统初始化
        # - 外部服务连接检查
        # - 游戏数据预加载

        logger.info("✅ TCG游戏服务器初始化完成")
        ChatClient.initialize_url_config(server_configuration)
        logger.info("✅ ChatClient URL配置已初始化")

    except Exception as e:
        logger.error(f"❌ 服务器初始化失败: {e}")
        raise

    yield  # 应用运行期间

    # 关闭时的清理操作
    logger.info("🔄 TCG游戏服务器关闭中...")

    # 在这里添加关闭时需要执行的清理操作
    try:
        # 可以在这里添加清理操作，比如：
        # - 关闭数据库连接
        # - 清理缓存
        # - 保存游戏状态
        # - 关闭外部服务连接

        logger.info("✅ TCG游戏服务器清理完成")

    except Exception as e:
        logger.error(f"❌ 服务器清理失败: {e}")


app = FastAPI(lifespan=lifespan)


@app.get(path="/")
async def get_api_info(request: Request) -> Dict[str, Any]:
    """API 根路由接口

    提供 API 服务的基本信息和所有可用端点的列表。

    Args:
        request: FastAPI 请求对象

    Returns:
        Dict[str, Any]: 包含服务信息、状态、可用端点列表和已注册路由的响应字典
    """
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
        "service": "AI RPG TCG Game Server",
        "base_url": base_url,
        "description": "AI RPG TCG Game Server API Root Endpoint",
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

# 公共的
app.include_router(router=player_session_api_router)
app.include_router(router=entity_details_api_router)
app.include_router(router=stages_state_api_router)
app.include_router(router=background_tasks_api_router)

# TCG特有的
app.include_router(router=login_api_router)
app.include_router(router=start_api_router)
app.include_router(router=home_gameplay_api_router)
app.include_router(router=dungeon_gameplay_api_router)
app.include_router(router=dungeon_state_api_router)


def main() -> None:

    setup_logger()

    logger.info(f"启动游戏服务器，端口: {server_configuration.game_server_port}")

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=server_configuration.game_server_port,
    )


if __name__ == "__main__":
    main()
