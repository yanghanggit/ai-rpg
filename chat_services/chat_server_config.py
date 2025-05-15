from pathlib import Path
from typing import List
from pydantic import BaseModel


##################################################################################################################
# 根目录
GEN_CONFIGS_DIR: Path = Path("gen_configs")
GEN_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
assert GEN_CONFIGS_DIR.exists(), f"找不到目录: {GEN_CONFIGS_DIR}"


##################################################################################################################
# 启动一个服务的配置原型
class ChatServerConfig(BaseModel):
    port: int = 8100
    temperature: float = 0.7
    api: str = "/v1/llm_serve/chat/"
    fast_api_title: str = "title1"
    fast_api_version: str = "0.0.1"
    fast_api_description: str = "description1"


##################################################################################################################
# 启动一个Agent的配置原型
class StartupConfiguration(BaseModel):
    name: str = ""
    service_configurations: List[ChatServerConfig] = []


##################################################################################################################
def localhost_urls() -> List[str]:
    chat_server_config = ChatServerConfig()
    return [f"http://localhost:{chat_server_config.port}{chat_server_config.api}"]
##################################################################################################################