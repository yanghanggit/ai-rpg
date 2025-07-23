import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, final
from jose import JWTError, jwt
from pydantic import BaseModel
from ..config.db_config import (
    JWT_SIGNING_ALGORITHM,
    JWT_SIGNING_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)


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
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)

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
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(
            days=REFRESH_TOKEN_EXPIRE_DAYS
        )  # 默认 7 天有效期
    to_encode.update({"exp": expire})
    encoded_jwt = _encode_jwt(to_encode)
    return encoded_jwt


############################################################################################################
def _encode_jwt(
    to_encode: dict[str, Any],
) -> str:
    try:
        encoded_jwt = jwt.encode(
            to_encode, JWT_SIGNING_KEY, algorithm=JWT_SIGNING_ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        print(f"JWT 编码失败: {e}")
        return ""


############################################################################################################
def decode_jwt(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SIGNING_KEY, algorithms=[JWT_SIGNING_ALGORITHM])
        return payload

    except JWTError:
        return {}


############################################################################################################
