"""
JWT (JSON Web Token) 认证模块

本模块提供基于 JWT 的身份认证和授权功能，包括访问令牌和刷新令牌的生成、编码和解码。
使用 python-jose 库实现 JWT 的签名和验证，确保令牌的安全性和完整性。

主要功能:
    - 创建访问令牌 (Access Token): 短期有效的身份凭证
    - 创建刷新令牌 (Refresh Token): 长期有效的令牌更新凭证
    - JWT 编码和解码: 安全的令牌生成和验证
    - 令牌撤销支持: 通过 JTI (JWT ID) 实现令牌唯一标识

安全特性:
    - HS256 签名算法
    - UTC 时区时间戳
    - 唯一令牌标识符 (JTI)
    - 可配置的过期时间

典型使用场景:
    1. 用户登录后生成访问令牌和刷新令牌
    2. 使用访问令牌进行 API 请求认证
    3. 访问令牌过期后使用刷新令牌获取新的访问令牌
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Final, Optional, final
from jose import jwt
from pydantic import BaseModel


############################################################################################################
# JWT 相关配置
@final
class JWTConfig(BaseModel):
    """
    JWT 配置类

    定义 JWT 生成和验证所需的配置参数，包括签名密钥、算法和过期时间。

    Attributes:
        signing_key: JWT 签名密钥，生产环境中应使用强随机密钥
        signing_algorithm: JWT 签名算法，默认使用 HS256
        refresh_token_expire_days: 刷新令牌的有效期（天）
        access_token_expire_minutes: 访问令牌的有效期（分钟）

    Security Note:
        在生产环境中必须修改 signing_key 为安全的随机密钥，
        建议使用环境变量或密钥管理服务来管理密钥。
    """

    signing_key: str = "your-secret-key-here-please-change-it"
    signing_algorithm: str = "HS256"
    refresh_token_expire_days: int = 7
    access_token_expire_minutes: int = 30


############################################################################################################
# 全局 JWT 配置实例
jwt_config: Final[JWTConfig] = JWTConfig()


############################################################################################################
# 数据模型
@final
class AuthTokenResponse(BaseModel):
    """
    认证令牌响应模型

    用于返回用户认证成功后的令牌信息，包含访问令牌和刷新令牌。

    Attributes:
        access_token: 访问令牌，用于 API 请求认证
        token_type: 令牌类型，通常为 "bearer"
        refresh_token: 刷新令牌，用于获取新的访问令牌

    Example:
        >>> response = AuthTokenResponse(
        ...     access_token="eyJ0eXAi...",
        ...     token_type="bearer",
        ...     refresh_token="eyJ0eXAi..."
        ... )
    """

    access_token: str
    token_type: str
    refresh_token: str


############################################################################################################
def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建访问令牌 (Access Token)

    生成一个短期有效的 JWT 访问令牌，用于 API 请求的身份认证。
    令牌包含用户数据、过期时间和唯一标识符 (JTI)。

    Args:
        data: 要编码到令牌中的数据字典，通常包含用户 ID 等信息
        expires_delta: 自定义过期时间间隔，如果不提供则使用默认的 15 分钟

    Returns:
        str: 编码后的 JWT 访问令牌字符串

    Example:
        >>> token = create_access_token({"sub": "user123"})
        >>> token = create_access_token(
        ...     {"sub": "user123"},
        ...     expires_delta=timedelta(hours=1)
        ... )

    Note:
        - 每个令牌都包含唯一的 JTI，可用于令牌撤销机制
        - 使用 UTC 时区确保时间一致性
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    # 添加一个唯一标识符用于令牌撤销
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "jti": jti})

    encoded_jwt = _encode_token_to_jwt(to_encode)
    return encoded_jwt


############################################################################################################
def create_refresh_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建刷新令牌 (Refresh Token)

    生成一个长期有效的 JWT 刷新令牌，用于获取新的访问令牌。
    刷新令牌的有效期通常比访问令牌长，减少用户重新登录的频率。

    Args:
        data: 要编码到令牌中的数据字典，通常包含用户 ID 等信息
        expires_delta: 自定义过期时间间隔，如果不提供则使用配置的默认值（7天）

    Returns:
        str: 编码后的 JWT 刷新令牌字符串

    Example:
        >>> refresh_token = create_refresh_token({"sub": "user123"})
        >>> refresh_token = create_refresh_token(
        ...     {"sub": "user123"},
        ...     expires_delta=timedelta(days=30)
        ... )

    Note:
        - 刷新令牌应当安全存储，避免泄露
        - 默认有效期为 7 天，可通过配置修改
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=jwt_config.refresh_token_expire_days
        )
    to_encode.update({"exp": expire})
    encoded_jwt = _encode_token_to_jwt(to_encode)
    return encoded_jwt


############################################################################################################
def _encode_token_to_jwt(
    to_encode: Dict[str, Any],
) -> str:
    """
    将数据载荷编码为 JWT 字符串（内部函数）

    使用配置的签名密钥和算法将数据字典编码为 JWT 格式的字符串。
    这是一个内部辅助函数，被 create_access_token 和 create_refresh_token 调用。

    Args:
        to_encode: 要编码的数据字典，包含令牌的所有声明 (claims)

    Returns:
        str: 编码后的 JWT 字符串

    Note:
        - 这是一个私有函数，不应直接从模块外部调用
        - 使用全局 jwt_config 中的签名密钥和算法
    """
    encoded_jwt = jwt.encode(
        to_encode,
        jwt_config.signing_key,
        algorithm=jwt_config.signing_algorithm,
    )
    return str(encoded_jwt)


############################################################################################################
def decode_jwt_token(token: str) -> Dict[str, Any]:
    """
    解码并验证 JWT 令牌

    验证 JWT 令牌的签名并解码其中的数据载荷。
    此函数会验证令牌的完整性、签名和过期时间。

    Args:
        token: 要解码的 JWT 令牌字符串

    Returns:
        Dict[str, Any]: 解码后的令牌数据字典，包含所有声明 (claims)

    Raises:
        JWTError: 当令牌无效、已过期或签名验证失败时抛出

    Example:
        >>> token = create_access_token({"sub": "user123"})
        >>> payload = decode_jwt_token(token)
        >>> print(payload["sub"])
        'user123'

    Note:
        - 自动验证令牌签名和过期时间
        - 调用方应处理可能的 JWTError 异常
    """
    payload = jwt.decode(
        token,
        jwt_config.signing_key,
        algorithms=[jwt_config.signing_algorithm],
    )
    return dict(payload)


############################################################################################################
