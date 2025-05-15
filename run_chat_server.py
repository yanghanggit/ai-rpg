# ##################################################################################################################
def main() -> None:

    from chat_services.chat_server import app
    from chat_services.chat_server_config import chat_service_api_port
    import uvicorn

    uvicorn.run(app, host="localhost", port=chat_service_api_port)


##################################################################################################################

if __name__ == "__main__":
    main()

##################################################################################################################
