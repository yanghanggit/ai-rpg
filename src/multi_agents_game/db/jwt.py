import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, final
from jose import JWTError, jwt
from pydantic import BaseModel
from ..config.db_config import DEFAULT_JWT_CONFIG


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
