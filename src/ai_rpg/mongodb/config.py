from typing import ClassVar, Final, final
from pydantic import BaseModel


##################################################################################################################
# MongoDB的配置
@final
class MongoDBConfig(BaseModel):
    host: str = "localhost"
    port: int = 27017
    database: str = "ai_rpg"
    username: str = ""
    password: str = ""

    # 集合名称配置 - 使用 ClassVar 标注类变量
    # worlds_boot_collection: ClassVar[str] = "worlds_boot"
    # worlds_collection: ClassVar[str] = "worlds"
    # dungeons_collection: ClassVar[str] = "dungeons"

    @property
    def connection_string(self) -> str:
        """获取MongoDB连接字符串"""
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            return f"mongodb://{self.host}:{self.port}/"


##################################################################################################################
# 默认配置实例
DEFAULT_MONGODB_CONFIG: Final[MongoDBConfig] = MongoDBConfig()


##################################################################################################################
