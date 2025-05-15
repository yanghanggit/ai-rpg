from typing import Final, List
from pydantic import BaseModel
from pathlib import Path


class ChatServerSettings(BaseModel):
    chat_service_base_port: int
    num_chat_service_instances: int


chat_server_setting_path: Path = Path("chat_server_settings.json")
assert (
    chat_server_setting_path.exists()
), f"chat_server_settings.json not found in {chat_server_setting_path.parent}"
chat_server_settings = ChatServerSettings.model_validate_json(
    chat_server_setting_path.read_text(encoding="utf-8")
)
assert (
    chat_server_settings.chat_service_base_port > 0
), "chat_service_base_port must be greater than 0"
assert (
    chat_server_settings.num_chat_service_instances > 0
), "num_chat_service_instances must be greater than 0"


##################################################################################################################
chat_service_path: Final[str] = "/chat-service/v1/"
chat_service_base_port: Final[int] = chat_server_settings.chat_service_base_port
num_chat_service_instances: Final[int] = chat_server_settings.num_chat_service_instances


##################################################################################################################
def chat_server_localhost_urls() -> List[str]:

    ret: List[str] = []
    for i in range(num_chat_service_instances):
        ret.append(f"http://localhost:{chat_service_base_port + i}{chat_service_path}")

    return ret


##################################################################################################################
