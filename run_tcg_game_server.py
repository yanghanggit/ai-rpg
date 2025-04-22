from fastapi.middleware.cors import CORSMiddleware
from services.game_server_instance import (
    GameServerInstance,
    initialize_game_server_instance,
)


###############################################################################################################################################
def main(game_server: GameServerInstance) -> None:
    import argparse
    import uvicorn

    from services.api_endpoints_services import api_endpoints_router
    from services.login_services import login_router
    from services.start_services import start_router
    from services.home_gameplay_services import home_gameplay_router
    from services.dungeon_gameplay_services import dungeon_gameplay_router
    from services.view_dungeon_services import view_dungeon_router
    from services.view_home_services import view_home_router
    from services.view_actor_services import view_actor_router

    game_server.fast_api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API Endpoints
    game_server.fast_api.include_router(router=api_endpoints_router)
    game_server.fast_api.include_router(router=login_router)
    game_server.fast_api.include_router(router=start_router)
    game_server.fast_api.include_router(router=home_gameplay_router)
    game_server.fast_api.include_router(router=dungeon_gameplay_router)
    game_server.fast_api.include_router(router=view_dungeon_router)
    game_server.fast_api.include_router(router=view_home_router)
    game_server.fast_api.include_router(router=view_actor_router)
    # 加一些其他的。。。。。

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
        host=str(args.host),
        port=int(args.port),
    )


if __name__ == "__main__":
    # 开局域网, 问题还是很多的，Unity可能涉及安全访问的问题。
    main(
        initialize_game_server_instance(
            server_ip_address="0.0.0.0",
            server_port=8000,
            local_network_ip="192.168.192.109",
        )
    )
