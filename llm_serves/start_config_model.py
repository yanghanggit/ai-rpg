from pydantic import BaseModel


# 启动一个服务的配置原型
class StartConfigModel(BaseModel):
    port: int = 8000
    temperature: float = 0.7
    api: str = "/v0/api/"
    fast_api_title: str = "title"
    fast_api_version: str = "0.0.1"
    fast_api_description: str = "description"
