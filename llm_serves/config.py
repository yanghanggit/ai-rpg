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
class ServiceConfiguration(BaseModel):
    port: int = 8000
    temperature: float = 0.7
    api: str = "/v0/api/"
    fast_api_title: str = "title"
    fast_api_version: str = "0.0.1"
    fast_api_description: str = "description"


##################################################################################################################
# 启动一个Agent的配置原型
class AgentStartupConfiguration(BaseModel):
    name: str = ""
    service_configurations: List[ServiceConfiguration] = []
