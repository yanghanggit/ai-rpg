# ##################################################################################################################
def main() -> None:

    from multi_agents_game.chat_services.chat_server_fastapi import app
    from multi_agents_game.config.server_config import (
        chat_service_base_port,
        num_chat_service_instances,
    )
    import uvicorn

    if num_chat_service_instances != 1:
        raise ValueError(
            "This script is only for running a single instance of the chat server."
        )
    uvicorn.run(app, host="localhost", port=chat_service_base_port)
    while True:
        pass


##################################################################################################################

if __name__ == "__main__":
    main()

##################################################################################################################


# lsof -i :8102
# kill -9 87600
