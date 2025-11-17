from typing import final
from pydantic import BaseModel


@final
class MongoConfig(BaseModel):
    host: str = "localhost"
    port: int = 27017
    database: str = "ai_rpg"

    @property
    def connection_string(self) -> str:
        """获取MongoDB连接字符串"""
        return f"mongodb://{self.host}:{self.port}/"


##################################################################################################################
