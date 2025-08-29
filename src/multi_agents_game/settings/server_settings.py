from pathlib import Path
from typing import List, Optional, final, Annotated
from pydantic import BaseModel
from fastapi import Depends


@final
class ServerSettings(BaseModel):
    azure_openai_chat_server_port: int = 8100
    game_server_port: int = 8000
    azure_openai_chat_service_api_endpoint: str = "/chat-service/v1/"

    @property
    def azure_openai_chat_server_localhost_urls(self) -> List[str]:
        return [
            f"http://localhost:{self.azure_openai_chat_server_port}{self.azure_openai_chat_service_api_endpoint}"
        ]


_server_settings: Optional[ServerSettings] = None


###############################################################################################################################################
def initialize_server_settings_instance(path: Path) -> ServerSettings:
    global _server_settings
    assert _server_settings is None, "ServerSettings is already initialized"
    if _server_settings is None:
        assert path.exists(), f"{path} must exist"
        content = path.read_text(encoding="utf-8")
        _server_settings = ServerSettings.model_validate_json(content)

    return _server_settings


###############################################################################################################################################
def get_server_setting_instance() -> ServerSettings:
    global _server_settings
    assert _server_settings is not None, "ServerSettings must be initialized"
    return _server_settings


###############################################################################################################################################
ServerSettingsInstance = Annotated[ServerSettings, Depends(get_server_setting_instance)]
