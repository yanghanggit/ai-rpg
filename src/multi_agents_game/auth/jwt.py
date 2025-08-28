import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Final, Optional, final

from jose import JWTError, jwt
from pydantic import BaseModel


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


DEFAULT_JWT_CONFIG: Final[JWTConfig] = JWTConfig()


############################################################################################################
# 数据模型
@final
class UserToken(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str  # 新增字段


############################################################################################################
# 创建JWT令牌
def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    # 添加一个唯一标识符用于令牌撤销 (新增)
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "jti": jti})

    encoded_jwt = _encode_jwt(to_encode)
    return encoded_jwt


############################################################################################################
def create_refresh_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=DEFAULT_JWT_CONFIG.refresh_token_expire_days
        )  # 默认 7 天有效期
    to_encode.update({"exp": expire})
    encoded_jwt = _encode_jwt(to_encode)
    return encoded_jwt


############################################################################################################
def _encode_jwt(
    to_encode: Dict[str, Any],
) -> str:
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            DEFAULT_JWT_CONFIG.signing_key,
            algorithm=DEFAULT_JWT_CONFIG.signing_algorithm,
        )
        return str(encoded_jwt)
    except Exception as e:
        print(f"JWT 编码失败: {e}")
        return ""

    return ""


############################################################################################################
def decode_jwt(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            DEFAULT_JWT_CONFIG.signing_key,
            algorithms=[DEFAULT_JWT_CONFIG.signing_algorithm],
        )
        return dict(payload)

    except JWTError:
        return {}


############################################################################################################
