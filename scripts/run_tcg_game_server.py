import os
from pathlib import Path
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from loguru import logger
from multi_agents_game.settings import (
    initialize_server_settings_instance,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from multi_agents_game.game_services.dungeon_gameplay_services import (
    dungeon_gameplay_router,
)
from multi_agents_game.game_services.home_gameplay_services import home_gameplay_router
from multi_agents_game.game_services.login_services import login_router
from multi_agents_game.game_services.start_services import start_router
from multi_agents_game.game_services.url_config_services import url_config_router
from multi_agents_game.game_services.view_actor_services import view_actor_router
from multi_agents_game.game_services.view_dungeon_services import view_dungeon_router
from multi_agents_game.game_services.view_home_services import view_home_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI应用生命周期管理
    处理应用启动和关闭时的初始化和清理操作
    """
    # 启动时的初始化操作
    logger.info("🚀 TCG游戏服务器启动中...")

    # 在这里添加启动时需要执行的初始化操作
    try:
        # 初始化服务器设置
        server_config = initialize_server_settings_instance(
            Path("server_settings.json")
        )
        logger.info(f"✅ 服务器配置已加载，端口: {server_config.game_server_port}")

        # 可以在这里添加其他初始化操作，比如：
        # - 数据库连接初始化
        # - 缓存系统初始化
        # - 外部服务连接检查
        # - 游戏数据预加载

        logger.info("✅ TCG游戏服务器初始化完成")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router=url_config_router)
app.include_router(router=login_router)
app.include_router(router=start_router)
app.include_router(router=home_gameplay_router)
app.include_router(router=dungeon_gameplay_router)
app.include_router(router=view_dungeon_router)
app.include_router(router=view_home_router)
app.include_router(router=view_actor_router)


def main() -> None:

    # 服务器配置在lifespan中已经初始化，这里直接获取
    server_config = initialize_server_settings_instance(Path("server_settings.json"))

    logger.info(f"启动游戏服务器，端口: {server_config.game_server_port}")
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=server_config.game_server_port,
    )


if __name__ == "__main__":
    main()
