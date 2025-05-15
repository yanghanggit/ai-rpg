from pathlib import Path
from typing import List
from pydantic import BaseModel


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
def localhost_urls() -> List[str]:
    chat_server_config = ChatServerConfig()
    return [f"http://localhost:{chat_server_config.port}{chat_server_config.api}"]


##################################################################################################################


##################################################################################################################
# 根目录
GEN_CONFIGS_DIR: Path = Path("gen_configs")
GEN_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
assert GEN_CONFIGS_DIR.exists(), f"找不到目录: {GEN_CONFIGS_DIR}"

chat_server_config = ChatServerConfig()
chat_server_config_path = GEN_CONFIGS_DIR / "chat_server_config.json"
chat_server_config_path.write_text(
    chat_server_config.model_dump_json(), encoding="utf-8"
)
print(f"配置文件已保存到: {chat_server_config_path}")
