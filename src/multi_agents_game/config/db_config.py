from typing import Final, final, ClassVar
from pydantic import BaseModel
import os


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

# JWT 相关配置
JWT_SIGNING_KEY: Final[str] = (
    "your-secret-key-here-please-change-it"  # 生产环境要用更复杂的密钥
)
JWT_SIGNING_ALGORITHM: Final[str] = "HS256"
REFRESH_TOKEN_EXPIRE_DAYS: Final[int] = 7
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = 30  # 访问令牌的过期时间，单位为分钟

##################################################################################################################
# 数据库配置
postgres_user: Final[str] = os.getenv("POSTGRES_USER", "yanghang")  # 使用实际的超级用户
postgres_password: Final[str] = os.getenv("POSTGRES_PASSWORD", "")  # 无密码认证
postgres_host: Final[str] = os.getenv("POSTGRES_HOST", "localhost")
postgres_db: Final[str] = os.getenv("POSTGRES_DB", "my_fastapi_db")

# 使用环境变量配置数据库连接，开发环境默认使用yanghang超级用户
POSTGRES_DATABASE_URL: Final[str] = (
    f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}/{postgres_db}"
    if postgres_password
    else f"postgresql://{postgres_user}@{postgres_host}/{postgres_db}"
)

##################################################################################################################
# 默认配置实例
DEFAULT_MONGODB_CONFIG: Final[MongoDBConfig] = MongoDBConfig()
##################################################################################################################
