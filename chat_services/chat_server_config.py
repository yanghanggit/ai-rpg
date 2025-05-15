from typing import Final, List

chat_service_path: Final[str] = "/chat-service/v1/"
chat_service_base_port: Final[int] = 8100
num_chat_service_instances: Final[int] = 3


##################################################################################################################
def localhost_urls() -> List[str]:

    ret: List[str] = []
    for i in range(num_chat_service_instances):
        ret.append(f"http://localhost:{chat_service_base_port + i}{chat_service_path}")

    return ret


##################################################################################################################
