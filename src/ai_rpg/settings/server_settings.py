from pathlib import Path
from typing import Optional, final
from pydantic import BaseModel


@final
class ServerSettings(BaseModel):
    game_server_port: int = 8000
    azure_openai_chat_server_port: int = 8100
    deepseek_chat_server_port: int = 8200
    image_generation_server_port: int = 8300
    chat_api_endpoint: str = "/api/chat/v1/"
    chat_rag_api_endpoint: str = "/api/chat/rag/v1/"
    chat_undefined_api_endpoint: str = "/api/chat/undefined/v1/"
    chat_mcp_api_endpoint: str = "/api/chat/mcp/v1/"


###############################################################################################################################################
_server_settings: Optional[ServerSettings] = None


###############################################################################################################################################
def initialize_server_settings_instance(path: Path) -> ServerSettings:
    global _server_settings
    if _server_settings is None:
        assert path.exists(), f"{path} must exist"
        content = path.read_text(encoding="utf-8")
        _server_settings = ServerSettings.model_validate_json(content)

    return _server_settings
