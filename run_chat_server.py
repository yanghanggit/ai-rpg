# ##################################################################################################################
def main() -> None:

    from chat_services.chat_server_fastapi import app
    from chat_services.chat_server_settings import (
        chat_service_base_port,
        num_chat_service_instances,
    )
    import uvicorn

    if num_chat_service_instances != 1:
        raise ValueError(
            "This script is only for running a single instance of the chat server."
        )
    uvicorn.run(app, host="localhost", port=chat_service_base_port)


##################################################################################################################

if __name__ == "__main__":
    main()

##################################################################################################################
