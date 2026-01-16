"""
用户认证依赖模块

提供 FastAPI 依赖注入函数，用于从 JWT 令牌中验证和提取当前认证用户。
支持 OAuth2 Bearer Token 认证方式。
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

    验证 JWT 令牌并返回当前认证用户的用户名。

    Args:
        token: JWT 令牌字符串

    Returns:
        str: 当前认证用户的用户名

    Raises:
        HTTPException(401): 令牌无效、过期或用户不存在
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
