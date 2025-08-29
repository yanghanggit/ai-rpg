import os
from pathlib import Path
import sys

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

app = FastAPI()

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

    # 加载服务器配置
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
