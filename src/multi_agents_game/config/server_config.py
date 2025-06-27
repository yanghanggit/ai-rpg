from typing import Final, List
from pydantic import BaseModel
from pathlib import Path


class ServerSettings(BaseModel):
    chat_service_base_port: int
    num_chat_service_instances: int
    game_server_port: int = 8000  # 默认值


# 配置文件路径
server_setting_path: Path = Path("server_settings.json")
assert (
    server_setting_path.exists()
), f"server_settings.json not found in {server_setting_path.parent}"
server_settings = ServerSettings.model_validate_json(
    server_setting_path.read_text(encoding="utf-8")
)
assert (
    server_settings.chat_service_base_port > 0
), "chat_service_base_port must be greater than 0"
assert (
    server_settings.num_chat_service_instances > 0
), "num_chat_service_instances must be greater than 0"
assert server_settings.game_server_port > 0, "game_server_port must be greater than 0"


##################################################################################################################
# 聊天服务器配置
##################################################################################################################
chat_service_path: Final[str] = "/chat-service/v1/"
chat_service_base_port: Final[int] = server_settings.chat_service_base_port
num_chat_service_instances: Final[int] = server_settings.num_chat_service_instances

# 游戏服务器配置
game_server_port: Final[int] = server_settings.game_server_port


##################################################################################################################
def chat_server_localhost_urls() -> List[str]:
    """获取所有聊天服务器的 URL 列表"""
    ret: List[str] = []
    for i in range(num_chat_service_instances):
        ret.append(f"http://localhost:{chat_service_base_port + i}{chat_service_path}")
    return ret


##################################################################################################################
