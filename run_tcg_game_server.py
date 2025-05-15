def main() -> None:

    from game_services.game_server_config import GameServerConfig
    from game_services.game_server_app import app
    import uvicorn

    game_server_config = GameServerConfig()
    uvicorn.run(
        app,
        host=game_server_config.server_ip_address,
        port=game_server_config.server_port,
    )


if __name__ == "__main__":
    main()
