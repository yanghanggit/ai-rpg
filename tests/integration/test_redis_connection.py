#!/usr/bin/env python3
"""
Redis 连接和基本操作测试

测试 Redis 连接的可用性和基本 CRUD 操作
包括：连接测试、SET/GET 操作、DELETE 操作和数据清理验证

Author: yanghanggit
Date: 2025-08-01
"""

from typing import Generator
import pytest
from loguru import logger

from src.multi_agents_game.redis.client import (
    redis_set,
    redis_get,
    redis_delete,
)


class TestRedisConnection:
    """Redis 连接和基本操作测试类"""

    def test_redis_connection_and_operations(self) -> None:
        """
        测试 Redis 连接和基本操作

        使用简单的 set/get 操作验证 Redis 连接的可用性
        """
        test_key = "test_redis_connection"
        test_value = "hello_redis_2025"

        try:
            logger.info("🔍 开始测试 Redis 连接...")

            # 测试 SET 操作
            logger.info(f"📝 设置测试键值: {test_key} = {test_value}")
            redis_set(test_key, test_value)

            # 测试 GET 操作
            logger.info(f"📖 读取测试键值: {test_key}")
            retrieved_value = redis_get(test_key)

            # 验证结果
            assert (
                retrieved_value == test_value
            ), f"Redis 连接测试失败! 期望值: {test_value}, 实际值: {retrieved_value}"
            logger.success(f"✅ Redis 连接测试成功! 读取到的值: {retrieved_value}")

            # 清理测试数据
            logger.info(f"🧹 清理测试数据: {test_key}")
            redis_delete(test_key)

            # 验证删除
            deleted_value = redis_get(test_key)
            assert (
                deleted_value is None
            ), f"测试数据清理失败，键值仍然存在: {deleted_value}"
            logger.success("✅ 测试数据清理成功!")

            logger.success("🎉 Redis 连接和基本操作测试全部通过!")

        except Exception as e:
            logger.error(f"❌ Redis 连接测试失败: {e}")
            raise

    def test_redis_set_get(self) -> None:
        """测试 Redis SET 和 GET 操作"""
        test_key = "test_set_get"
        test_value = "test_value_123"

        # 设置值
        redis_set(test_key, test_value)

        # 获取值并验证
        retrieved_value = redis_get(test_key)
        assert retrieved_value == test_value

        # 清理
        redis_delete(test_key)

    def test_redis_delete(self) -> None:
        """测试 Redis DELETE 操作"""
        test_key = "test_delete"
        test_value = "to_be_deleted"

        # 设置值
        redis_set(test_key, test_value)

        # 验证值存在
        assert redis_get(test_key) == test_value

        # 删除值
        redis_delete(test_key)

        # 验证值已删除
        assert redis_get(test_key) is None

    def test_redis_nonexistent_key(self) -> None:
        """测试获取不存在的键"""
        nonexistent_key = "definitely_does_not_exist_12345"

        # 确保键不存在
        redis_delete(nonexistent_key)

        # 获取不存在的键应该返回 None
        result = redis_get(nonexistent_key)
        assert result is None

    @pytest.fixture(autouse=True)
    def cleanup_test_keys(self) -> Generator[None, None, None]:
        """测试后自动清理测试键"""
        test_keys = [
            "test_redis_connection",
            "test_set_get",
            "test_delete",
            "definitely_does_not_exist_12345",
        ]

        yield  # 运行测试

        # 清理所有测试键
        for key in test_keys:
            try:
                redis_delete(key)
            except Exception:
                pass  # 忽略清理错误
