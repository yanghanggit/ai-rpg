"""
用户认证依赖模块

本模块提供 FastAPI 依赖注入函数，用于从 JWT 令牌中验证和提取当前认证用户。
通过 OAuth2 密码流程（Password Flow）实现用户身份验证，支持 Bearer Token 认证方式。

主要功能:
    - JWT 令牌验证和解码
    - 用户身份提取和验证
    - FastAPI 依赖注入集成
    - 类型安全的用户认证

认证流程:
    1. 从请求头中提取 Bearer Token
    2. 验证 JWT 令牌的签名和有效期
    3. 提取令牌中的用户标识
    4. 验证用户在数据库中的存在性
    5. 返回当前认证用户的用户名

使用方式:
    # 方式1: 使用 Depends 显式注入
    @app.get("/api/user/profile")
    async def get_profile(username: str = Depends(get_current_user)):
        return {"user": username}

    # 方式2: 使用类型别名（推荐）
    @app.get("/api/user/profile")
    async def get_profile(username: CurrentUser):
        return {"user": username}
"""

from typing import Annotated, Final, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from ..auth.jwt import decode_jwt_token
from ..pgsql.user_operations import get_user, has_user

# OAuth2 密码流程的令牌获取端点
oauth2_scheme: Final[OAuth2PasswordBearer] = OAuth2PasswordBearer(tokenUrl="token")


###################################################################################################################################################################
async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    获取当前认证用户（FastAPI 依赖注入函数）

    此函数作为 FastAPI 的依赖项，自动从 HTTP 请求头中提取 Bearer Token，
    验证 JWT 令牌的有效性，并返回当前认证用户的用户名。

    认证步骤:
        1. 解码并验证 JWT 令牌的签名和有效期
        2. 从令牌载荷中提取用户标识（sub 字段）
        3. 验证用户在数据库中是否存在
        4. 返回用户名

    Args:
        token: JWT 令牌字符串，由 oauth2_scheme 自动从请求头提取

    Returns:
        str: 当前认证用户的用户名

    Raises:
        HTTPException(401): 以下情况会抛出 401 未授权错误
            - JWT 令牌格式无效或签名验证失败
            - 令牌已过期
            - 令牌中缺少用户标识
            - 用户在数据库中不存在

    Example:
        >>> # 在路由中使用
        >>> @app.get("/api/protected")
        >>> async def protected_route(username: str = Depends(get_current_user)):
        ...     return {"current_user": username}
        >>>
        >>> # 或使用类型别名
        >>> @app.get("/api/protected")
        >>> async def protected_route(username: CurrentUser):
        ...     return {"current_user": username}

    Note:
        - FastAPI 会自动调用此依赖函数，异常会被转换为 HTTP 响应
        - 所有认证失败都返回 401 状态码，避免信息泄露
        - 支持标准的 OAuth2 Bearer Token 认证方式
    """
    # 解码并验证 JWT 令牌
    try:
        payload = decode_jwt_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 提取用户名
    username: Optional[str] = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证用户是否存在
    if not has_user(username):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 获取并返回用户信息
    user_db = get_user(username)
    return user_db.username


###################################################################################################################################################################
# 类型注解别名，简化依赖注入的使用
#
# 使用方式:
#   @app.get("/api/user/info")
#   async def user_info(username: CurrentUser):
#       return {"username": username}
#
# 等价于:
#   async def user_info(username: str = Depends(get_current_user)):
#
CurrentUser = Annotated[str, Depends(get_current_user)]


###################################################################################################################################################################
