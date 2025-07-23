from . import redis_client
from .jwt import UserToken


###############################################################################################################################################
def _user_access_token_key(username: str) -> str:
    """生成用户会话键名"""
    assert username != "", "username cannot be an empty string."
    return f"user_token:{username}"


###############################################################################################################################################
def _blacklist_access_token_key(token_id: str) -> str:
    """生成令牌黑名单键名"""
    assert token_id != "", "token_id cannot be an empty string."
    return f"blacklist:{token_id}"


###############################################################################################################################################
def _user_displaye_name_key(username: str) -> str:
    """生成用户显示名称键名"""
    assert username != "", "token_id cannot be an empty string."
    return f"display_name:{username}"


###############################################################################################################################################
def assign_user_access_token(username: str, token: UserToken) -> None:
    user_token_key = _user_access_token_key(username)
    redis_client.redis_delete(user_token_key)
    redis_client.redis_hset(user_token_key, token.model_dump())
    redis_client.redis_expire(user_token_key, seconds=60)  # 设置过期时间为1小时


###############################################################################################################################################
def is_user_access_token_present(username: str) -> bool:
    user_token_key = _user_access_token_key(username)
    return redis_client.redis_exists(user_token_key)


###############################################################################################################################################
def remove_user_access_token(username: str) -> None:
    """
    从Redis中删除用户的令牌

    参数:
        username: 用户名
    """
    user_token_key = _user_access_token_key(username)
    redis_client.redis_delete(user_token_key)


###############################################################################################################################################
def add_access_token_to_blacklist(token_id: str, expire_seconds: int) -> None:
    """
    将令牌ID添加到黑名单中，并设置过期时间

    参数:
        token_id: JWT令牌的唯一标识符(jti)
        expire_seconds: 令牌过期前的剩余秒数
    """
    blacklist_key = _blacklist_access_token_key(token_id)
    # 使用字符串值"1"表示该令牌已被拉黑，并在一次操作中设置过期时间
    redis_client.redis_setex(blacklist_key, expire_seconds, "1")


###############################################################################################################################################
def is_access_token_blacklisted(token_id: str) -> bool:
    """
    检查令牌是否在黑名单中

    参数:
        token_id: JWT令牌的唯一标识符(jti)

    返回:
        bool: 如果令牌在黑名单中则返回True，否则返回False
    """
    blacklist_key = _blacklist_access_token_key(token_id)
    return redis_client.redis_exists(blacklist_key)


###############################################################################################################################################
def set_user_display_name(username: str, display_name: str) -> None:
    """
    设置用户的显示名称
    参数:
        username: 用户名
        display_name: 用户的显示名称
    该函数将用户的显示名称存储在Redis中，键名为"display_name:{username}"。
    """
    display_name_key = _user_displaye_name_key(username)
    redis_client.redis_set(display_name_key, display_name)


###############################################################################################################################################
def get_user_display_name(username: str) -> str:
    """
    获取用户的显示名称
    参数:
        username: 用户名
    返回:
        str: 用户的显示名称，如果不存在则返回空字符串
    该函数从Redis中获取用户的显示名称，键名为"display_name:{username}"。
    """
    display_name_key = _user_displaye_name_key(username)
    return redis_client.redis_get(display_name_key) or ""


###############################################################################################################################################
