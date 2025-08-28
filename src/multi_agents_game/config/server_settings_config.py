from typing import Final, List, final
from pydantic import BaseModel


@final
class ServerSettingsConfig(BaseModel):
    azure_openai_chat_server_port: int = 8100
    game_server_port: int = 8000
    azure_openai_chat_service_api_endpoint: str = "/chat-service/v1/"

    @property
    def azure_openai_chat_server_localhost_urls(self) -> List[str]:
        return [
            f"http://localhost:{self.azure_openai_chat_server_port}{self.azure_openai_chat_service_api_endpoint}"
        ]


##################################################################################################################
DEFAULT_SERVER_SETTINGS_CONFIG: Final[ServerSettingsConfig] = ServerSettingsConfig()

##################################################################################################################
