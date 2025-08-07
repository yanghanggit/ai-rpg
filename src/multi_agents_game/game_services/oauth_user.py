from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from ..db.jwt import UserToken, decode_jwt
from ..db.pgsql_user import get_user, has_user
from ..db.redis_user import (
    assign_user_access_token,
    is_access_token_blacklisted,
    is_user_access_token_present,
)

# 获取当前用户
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_authenticated_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = decode_jwt(token)
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭证",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 检查令牌是否在黑名单中 (新增)
        if "jti" in payload:
            jti = payload.get("jti")
            if jti is not None and is_access_token_blacklisted(str(jti)):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="令牌已被撤销",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        if is_user_access_token_present(username):
            # 如果 Redis 中存在用户令牌，直接返回用户名
            return username

        # 检查用户是否存在
        if not has_user(username):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        # 获取用户信息
        user_db = get_user(username)
        assign_user_access_token(
            user_db.username,
            UserToken(
                access_token=token,
                token_type="bearer",
                refresh_token="",  # 假设没有刷新令牌
            ),
        )
        return user_db.username

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
