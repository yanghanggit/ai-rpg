from typing import Final, final
from pydantic import BaseModel


@final
class MongoDBConfig(BaseModel):
    host: str = "localhost"
    port: int = 27017
    database: str = "ai_rpg"
    username: str = ""
    password: str = ""

    @property
    def connection_string(self) -> str:
        """获取MongoDB连接字符串"""
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            return f"mongodb://{self.host}:{self.port}/"


##################################################################################################################
# 默认配置实例
mongodb_config: Final[MongoDBConfig] = MongoDBConfig()


##################################################################################################################
