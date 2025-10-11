from typing import Final, final
from pydantic import BaseModel


##################################################################################################################
# PostgreSQL的配置
@final
class PostgreSQLConfig(BaseModel):
    host: str = "localhost"
    database: str = "my_fastapi_db"
    user: str = "postgres"
    password: str = ""

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
DEFAULT_POSTGRESQL_CONFIG: Final[PostgreSQLConfig] = PostgreSQLConfig()


##################################################################################################################
