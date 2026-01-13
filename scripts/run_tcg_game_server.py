import os
from pathlib import Path
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Final

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
from ai_rpg.models import RootResponse
from datetime import datetime
from ai_rpg.services.entity_details import (
    entity_details_api_router,
)
from ai_rpg.services.dungeon_state import dungeon_state_api_router
from ai_rpg.services.stages_state import stages_state_api_router
from ai_rpg.services.background_tasks import background_tasks_api_router
from ai_rpg.chat_services.client import ChatClient
from ai_rpg.services.player_session import player_session_api_router

_server_setting_path: Final[Path] = Path("server_configuration.json")
assert _server_setting_path.exists(), f"{_server_setting_path} must exist"


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


@app.get(path="/", response_model=RootResponse)
async def root(request: Request) -> RootResponse:
    """API 根路由接口

    提供 API 服务的基本信息和所有可用端点的列表。
    客户端可以通过此接口发现和访问所有可用的 API 服务。

    Args:
        request: FastAPI 请求对象，用于日志记录请求来源

    Returns:
        RootResponse: API 根响应对象，包含以下信息：
            - service: 服务名称
            - description: 服务描述
            - status: 服务健康状态
            - timestamp: 当前时间戳
            - version: API 版本号
            - endpoints: 所有可用的 API 端点（相对路径格式，如 /api/login/v1/）

    Note:
        - 端点以相对路径形式返回，客户端需根据实际服务地址组合完整 URL
        - 返回的端点列表包括 RPG 游戏、狼人杀游戏和通用服务三大类
        - 此接口通常用于 API 文档生成和客户端服务发现
    """
    base_url = str(request.base_url)
    logger.info(f"获取API路由 RootResponse: {base_url}")

    return RootResponse(
        service="AI RPG TCG Game Server",
        description="AI RPG TCG Game Server API Root Endpoint",
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="0.0.1",
        endpoints={
            # rpg 专用
            "login": "/api/login/v1/",
            "logout": "/api/logout/v1/",
            "start": "/api/start/v1/",
            "home_gameplay": "/api/home/gameplay/v1/",
            "home_advance": "/api/home/advance/v1/",
            "home_trans_dungeon": "/api/home/trans_dungeon/v1/",
            "dungeon_gameplay": "/api/dungeon/gameplay/v1/",
            "dungeon_combat_play_cards": "/api/dungeon/combat/play_cards/v1/",
            "dungeon_trans_home": "/api/dungeon/trans_home/v1/",
            "dungeon_state": "/api/dungeons/v1/",
            # 通用的服务。
            "session_messages": "/api/session_messages/v1/",
            "entity_details": "/api/entities/v1/",
            "stages_state": "/api/stages/v1/",
            "tasks_trigger": "/api/tasks/v1/trigger",
            "tasks_status": "/api/tasks/v1/status",
        },
        api_docs={
            # 需要路径参数的端点完整路径说明
            "session_messages": "/api/session_messages/v1/{user_name}/{game_name}/since?last_sequence_id=0",
            "entity_details": "/api/entities/v1/{user_name}/{game_name}/details?entities=entity1&entities=entity2",
            "stages_state": "/api/stages/v1/{user_name}/{game_name}/state",
            "dungeon_state": "/api/dungeons/v1/{user_name}/{game_name}/state",
            "tasks_status": "/api/tasks/v1/status?task_ids=task_id1&task_ids=task_id2",
        },
    )


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

    logger.info(f"启动游戏服务器，端口: {server_configuration.game_server_port}")
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=server_configuration.game_server_port,
    )


if __name__ == "__main__":
    main()
