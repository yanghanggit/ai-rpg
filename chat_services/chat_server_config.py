from typing import Final, List

chat_service_api: Final[str] = "/chat-service/v1/"
chat_service_api_port: Final[int] = 8100


##################################################################################################################
def localhost_urls() -> List[str]:
    return [f"http://localhost:{chat_service_api_port}{chat_service_api}"]


##################################################################################################################
