from loguru import logger
from multi_agents_game.config.server_config import game_server_port
from multi_agents_game.game_services.game_server_fastapi import app


def main() -> None:
    logger.info(f"启动游戏服务器，端口: {game_server_port}")
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=game_server_port,
    )


if __name__ == "__main__":
    main()
