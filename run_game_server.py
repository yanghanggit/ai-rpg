from typing import cast
from services.room_manager import RoomManager
from services.game_server import ServerConfig
from services.game_server import GameServer
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI


###############################################################################################################################################
GameServer.Instance = GameServer(
    fast_api=FastAPI(),
    room_manager=RoomManager(),
    server_config=ServerConfig(server_ip_address="127.0.0.1", server_port=8000),
)


###############################################################################################################################################
def main(game_server: GameServer) -> None:
    import argparse
    import uvicorn
    from services.api_endpoints_services import api_endpoints_router
    from services.game_process_services import game_process_api_router
    from services.game_play_services import game_play_api_router

    game_server.fast_api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API Endpoints
    game_server.fast_api.include_router(router=api_endpoints_router)
    game_server.fast_api.include_router(router=game_process_api_router)
    game_server.fast_api.include_router(router=game_play_api_router)

    parser = argparse.ArgumentParser(description="启动 FastAPI 应用")
    parser.add_argument(
        "--host",
        type=str,
        default=game_server._server_config.server_ip_address,
        help="主机地址",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=game_server._server_config.server_port,
        help="端口号",
    )
    args = parser.parse_args()

    # 启动 FastAPI 应用
    print(
        f"!!!!启动 FastAPI 应用在 {args.host}:{args.port}!!!!!!!, pid={game_server.pid}"
    )
    uvicorn.run(
        game_server.fast_api,
        host=cast(str, args.host),
        port=cast(int, args.port),
    )


if __name__ == "__main__":
    main(GameServer.Instance)
