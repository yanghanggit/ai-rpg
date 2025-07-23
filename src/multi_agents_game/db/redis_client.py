from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Union, cast

import redis
from loguru import logger

from ..config.db_config import RedisConfig

# Redis键值类型定义
RedisKeyType = Union[str, bytes]
RedisValueType = Union[str, bytes, int, float]

# 为Redis客户端定义明确的类型
if TYPE_CHECKING:
    from redis import Redis

    RedisClientType = Redis[str]
else:
    RedisClientType = redis.Redis


###################################################################################################
def get_redis() -> RedisClientType:
    """
    获取Redis连接实例。

    返回:
        RedisClientType: Redis客户端实例，已配置为返回字符串
    """
    redis_config = RedisConfig()
    pool = redis.ConnectionPool(
        host=redis_config.host,
        port=redis_config.port,
        db=redis_config.db,
        decode_responses=True,
        # max_connections=20
    )
    return cast(RedisClientType, redis.Redis(connection_pool=pool))


###################################################################################################
# 获取Redis客户端的单例实例 - 用于直接调用
_redis_instance: Optional[RedisClientType] = None


###################################################################################################
def _get_redis_instance() -> RedisClientType:
    """
    获取Redis客户端单例实例。

    返回:
        RedisClient: Redis客户端实例
    """
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = get_redis()
    return _redis_instance


###################################################################################################
def redis_hset(name: str, mapping_data: Mapping[str, RedisValueType]) -> None:
    """
    设置Redis哈希表的多个字段。

    参数:
        name: 键名
        mapping_data: 要设置的字段-值映射

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        # 直接使用mapping_data，不需要转换
        redis_client.hset(name=name, mapping=mapping_data)  # type: ignore[arg-type]
    except redis.RedisError as e:
        logger.error(f"Redis error while setting data for {name}: {e}")
        raise e


###################################################################################################
def redis_hgetall(name: str) -> Dict[str, str]:
    """
    获取Redis哈希表中的所有字段和值。

    参数:
        name: 键名

    返回:
        Dict[str, str]: 哈希表中的字段和值

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        if not redis_client.exists(name):
            return {}
        result = redis_client.hgetall(name)
        return {} if result is None else result
    except redis.RedisError as e:
        logger.error(f"Redis error while getting data for {name}: {e}")
        raise e


###################################################################################################
def redis_delete(name: str) -> None:
    """
    删除Redis中的键。

    参数:
        name: 要删除的键名

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        redis_client.delete(name)
    except redis.RedisError as e:
        logger.error(f"Redis error while deleting data for {name}: {e}")
        raise e


###################################################################################################
def redis_lrange(name: str, start: int = 0, end: int = -1) -> List[str]:
    """
    获取Redis列表中指定范围内的元素。

    参数:
        name: 列表键名
        start: 起始索引（默认为0）
        end: 结束索引（默认为-1，表示最后一个元素）

    返回:
        List[str]: 指定范围内的列表元素

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        if not redis_client.exists(name):
            return []
        result = redis_client.lrange(name, start, end)
        return [] if result is None else result
    except redis.RedisError as e:
        logger.error(f"Redis error while getting list range for {name}: {e}")
        raise e


###################################################################################################
def redis_rpush(name: str, *values: str) -> int:
    """
    将一个或多个值添加到Redis列表的右侧。

    参数:
        name: 列表键名
        values: 要添加的值

    返回:
        int: 操作后列表的长度

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        return redis_client.rpush(name, *values)
    except redis.RedisError as e:
        logger.error(f"Redis error while pushing to list {name}: {e}")
        raise e


###################################################################################################
def redis_flushall() -> None:
    """
    清空Redis数据库中的所有数据。

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        redis_client.flushall()
    except redis.RedisError as e:
        logger.error(f"Redis error while flushing all data: {e}")
        raise e


###################################################################################################
def redis_exists(name: str) -> bool:
    """
    检查Redis中是否存在指定的键。

    参数:
        name: 键名

    返回:
        bool: 如果键存在则返回True，否则返回False

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        return redis_client.exists(name) > 0
    except redis.RedisError as e:
        logger.error(f"Redis error while checking existence of {name}: {e}")
        raise e


###################################################################################################
def redis_expire(name: str, seconds: int) -> bool:
    """
    为Redis中的键设置过期时间。

    参数:
        name: 键名
        seconds: 过期时间（秒）

    返回:
        bool: 设置成功返回True，键不存在返回False

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        return redis_client.expire(name, seconds)
    except redis.RedisError as e:
        logger.error(f"Redis error while setting expiry for {name}: {e}")
        raise e


###################################################################################################
def redis_setex(name: str, seconds: int, value: RedisValueType) -> bool:
    """
    设置Redis键的值，并设置过期时间。

    参数:
        name: 键名
        value: 要设置的值
        seconds: 过期时间（秒）

    返回:
        bool: 设置成功返回True，键不存在返回False

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        return redis_client.setex(name, seconds, value)
    except redis.RedisError as e:
        logger.error(f"Redis error while setting value for {name}: {e}")
        raise e


###################################################################################################
def redis_set(name: str, value: RedisValueType) -> bool | None:
    """
    设置Redis键的值。

    参数:
        name: 键名
        value: 要设置的值

    返回:
        bool: 设置成功返回True，键不存在返回False

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        return redis_client.set(name, value)
    except redis.RedisError as e:
        logger.error(f"Redis error while setting value for {name}: {e}")
        raise e


###################################################################################################
def redis_get(name: str) -> Optional[str]:
    """
    获取Redis中指定键的值。

    参数:
        name: 键名

    返回:
        Optional[str]: 如果键存在则返回其值，否则返回None

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        if not redis_client.exists(name):
            return None
        return redis_client.get(name)
    except redis.RedisError as e:
        logger.error(f"Redis error while getting value for {name}: {e}")
        raise e


###################################################################################################
def redis_hmset(name: str, mapping_data: Mapping[str, RedisValueType]) -> None:
    """
    设置Redis哈希表的多个字段。

    参数:
        name: 键名
        mapping_data: 要设置的字段-值映射

    抛出:
        redis.RedisError: 当Redis操作失败时
    """
    try:
        redis_client = _get_redis_instance()
        # 直接使用mapping_data，不需要转换
        redis_client.hmset(name=name, mapping=mapping_data)  # type: ignore[arg-type]
    except redis.RedisError as e:
        logger.error(f"Redis error while setting data for {name}: {e}")
        raise e


###################################################################################################
