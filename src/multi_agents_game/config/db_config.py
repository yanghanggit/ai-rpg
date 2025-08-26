import os
from typing import Any, ClassVar, Final, final

from pydantic import BaseModel


##################################################################################################################
# MongoDB的配置
@final
class MongoDBConfig(BaseModel):
    host: str = "localhost"
    port: int = 27017
    database: str = "multi_agents_game"
    username: str = ""
    password: str = ""

    # 集合名称配置 - 使用 ClassVar 标注类变量
    worlds_boot_collection: ClassVar[str] = "worlds_boot"
    worlds_collection: ClassVar[str] = "worlds"

    @property
    def connection_string(self) -> str:
        """获取MongoDB连接字符串"""
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            return f"mongodb://{self.host}:{self.port}/"


##################################################################################################################
# PostgreSQL的配置
@final
class PostgresConfig(BaseModel):
    host: str = "localhost"
    database: str = "my_fastapi_db"
    user: str = "postgres"
    password: str = ""

    def __init__(self, **kwargs: Any) -> None:
        # 从环境变量读取配置，如果没有则使用默认值
        super().__init__(
            host=os.getenv("POSTGRES_HOST", kwargs.get("host", "localhost")),
            database=os.getenv("POSTGRES_DB", kwargs.get("database", "my_fastapi_db")),
            user=os.getenv("POSTGRES_USER", kwargs.get("user", "postgres")),
            password=os.getenv("POSTGRES_PASSWORD", kwargs.get("password", "")),
        )

    @property
    def connection_string(self) -> str:
        """获取PostgreSQL连接字符串"""
        if self.password:
            return (
                f"postgresql://{self.user}:{self.password}@{self.host}/{self.database}"
            )
        else:
            return f"postgresql://{self.user}@{self.host}/{self.database}"


##################################################################################################################


##################################################################################################################
# 默认配置实例
# DEFAULT_REDIS_CONFIG: Final[RedisConfig] = RedisConfig()
DEFAULT_MONGODB_CONFIG: Final[MongoDBConfig] = MongoDBConfig()
DEFAULT_POSTGRES_CONFIG: Final[PostgresConfig] = PostgresConfig()


##################################################################################################################
