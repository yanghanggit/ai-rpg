from loguru import logger
from src.multi_agents_game.config import (
    DEFAULT_SERVER_SETTINGS_CONFIG,
)
from src.multi_agents_game.game_services.game_server_fastapi import app


def main() -> None:
    logger.info(
        f"启动游戏服务器，端口: {DEFAULT_SERVER_SETTINGS_CONFIG.game_server_port}"
    )
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=DEFAULT_SERVER_SETTINGS_CONFIG.game_server_port,
    )


if __name__ == "__main__":
    main()
