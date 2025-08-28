import os
from pathlib import Path
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from loguru import logger

from multi_agents_game.settings import (
    ServerSettings,
)
from multi_agents_game.game_services.game_server_fastapi import app


def main() -> None:

    write_path = Path("server_settings.json")
    assert write_path.exists(), "server_settings.json must exist"
    content = write_path.read_text(encoding="utf-8")
    server_config = ServerSettings.model_validate_json(content)

    logger.info(f"启动游戏服务器，端口: {server_config.game_server_port}")
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=server_config.game_server_port,
    )


if __name__ == "__main__":
    main()
