import os
from typing import Any, Final, final
from pydantic import BaseModel


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
DEFAULT_POSTGRES_CONFIG: Final[PostgresConfig] = PostgresConfig()


##################################################################################################################
