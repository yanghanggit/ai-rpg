from typing import Final, final
from pydantic import BaseModel


@final
class PostgreSQLConfig(BaseModel):
    host: str = "localhost"
    database: str = "ai-rpg-db"
    user: str = "postgres"

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}@{self.host}/{self.database}"


# 默认配置实例
postgresql_config: Final[PostgreSQLConfig] = PostgreSQLConfig()
