import os
from typing import Any, ClassVar, Final, final

from pydantic import BaseModel


##################################################################################################################
# redis的配置
@final
class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0


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
# JWT 相关配置
@final
class JWTConfig(BaseModel):
    signing_key: str = "your-secret-key-here-please-change-it"
    signing_algorithm: str = "HS256"
    refresh_token_expire_days: int = 7
    access_token_expire_minutes: int = 30

    def __init__(self, **kwargs: Any) -> None:
        # 从环境变量读取配置，如果没有则使用默认值
        super().__init__(
            signing_key=os.getenv(
                "JWT_SIGNING_KEY",
                kwargs.get("signing_key", "your-secret-key-here-please-change-it"),
            ),
            signing_algorithm=os.getenv(
                "JWT_SIGNING_ALGORITHM", kwargs.get("signing_algorithm", "HS256")
            ),
            refresh_token_expire_days=int(
                os.getenv(
                    "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
                    str(kwargs.get("refresh_token_expire_days", 7)),
                )
            ),
            access_token_expire_minutes=int(
                os.getenv(
                    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
                    str(kwargs.get("access_token_expire_minutes", 30)),
                )
            ),
        )


##################################################################################################################
# 默认配置实例
DEFAULT_REDIS_CONFIG: Final[RedisConfig] = RedisConfig()
DEFAULT_MONGODB_CONFIG: Final[MongoDBConfig] = MongoDBConfig()
DEFAULT_POSTGRES_CONFIG: Final[PostgresConfig] = PostgresConfig()
DEFAULT_JWT_CONFIG: Final[JWTConfig] = JWTConfig()
##################################################################################################################
