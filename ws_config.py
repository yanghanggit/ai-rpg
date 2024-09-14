from enum import Enum
from pydantic import BaseModel


class WS_CONFIG(Enum):
    Host = "127.0.0.1"
    Port = 8080


# 定义接收的数据模型
class TestData(BaseModel):
    message: str
