#!/usr/bin/env python3
"""
PostgreSQL 连接和基本操作测试

测试 PostgreSQL 连接的可用性和基本用户 CRUD 操作
包括：连接测试、用户创建、查询、存在性检查和数据清理

Author: yanghanggit
Date: 2025-08-01
"""

from typing import Generator

import pytest
from loguru import logger
from sqlalchemy import text

from ai_rpg.pgsql.client import SessionLocal
from ai_rpg.pgsql.user import UserDB
from ai_rpg.pgsql.user_operations import get_user, has_user, save_user


class TestPostgreSQLConnection:
    """PostgreSQL 连接和基本操作测试类"""

    def test_postgresql_connection_and_operations(self) -> None:
        """
        测试 PostgreSQL 连接和基本操作

        使用简单的用户 CRUD 操作验证 PostgreSQL 连接的可用性
        """
        test_username = "test_postgresql_connection"
        test_password = "test_password_2025"
        test_display_name = "Test User PostgreSQL"

        try:
            logger.info("🔍 开始测试 PostgreSQL 连接...")

            # 1. 测试数据库连接
            logger.info("📡 测试数据库连接...")
            db = SessionLocal()
            try:
                # 执行简单查询验证连接
                result = db.execute(text("SELECT 1 as test_connection")).fetchone()
                assert result and result[0] == 1, "PostgreSQL 数据库连接验证失败!"
                logger.success("✅ PostgreSQL 数据库连接成功!")
            finally:
                db.close()

            # 2. 测试用户创建操作
            logger.info(f"👤 创建测试用户: {test_username}")
            created_user = save_user(
                username=test_username,
                hashed_password=test_password,
                display_name=test_display_name,
            )

            assert (
                created_user and created_user.username == test_username
            ), "用户创建失败!"
            logger.success(f"✅ 用户创建成功! 用户ID: {created_user.id}")

            # 3. 测试用户查询操作
            logger.info(f"🔍 查询测试用户: {test_username}")
            found_user = get_user(test_username)

            assert (
                found_user
                and found_user.username == test_username
                and found_user.hashed_password == test_password
                and found_user.display_name == test_display_name
            ), "用户查询失败或数据不匹配!"
            logger.success(f"✅ 用户查询成功! 显示名: {found_user.display_name}")

            # 4. 测试用户存在性检查
            logger.info(f"🔎 检查用户是否存在: {test_username}")
            user_exists = has_user(test_username)

            assert user_exists, "用户存在性检查失败!"
            logger.success("✅ 用户存在性检查通过!")

            logger.success("🎉 PostgreSQL 连接和基本操作测试全部通过!")

        except Exception as e:
            logger.error(f"❌ PostgreSQL 连接测试失败: {e}")
            raise
        finally:
            # 5. 清理测试数据
            logger.info(f"🧹 清理测试数据: {test_username}")
            self._cleanup_test_user(test_username)

    def test_database_connection(self) -> None:
        """测试数据库连接"""
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT 1 as test")).fetchone()
            assert result and result[0] == 1
            logger.info("✅ 数据库连接测试通过")
        finally:
            db.close()

    def test_user_crud_operations(self) -> None:
        """测试用户 CRUD 操作"""
        test_username = "test_crud_user"
        test_password = "test_password"
        test_display_name = "Test CRUD User"

        try:
            # 确保用户不存在
            assert not has_user(test_username), "测试开始前用户不应该存在"

            # 创建用户
            created_user = save_user(
                username=test_username,
                hashed_password=test_password,
                display_name=test_display_name,
            )
            assert created_user is not None
            assert created_user.username == test_username

            # 检查用户存在
            assert has_user(test_username), "用户创建后应该存在"

            # 查询用户
            found_user = get_user(test_username)
            assert found_user is not None
            assert found_user.username == test_username
            assert found_user.hashed_password == test_password
            assert found_user.display_name == test_display_name

            logger.info("✅ 用户 CRUD 操作测试通过")

        finally:
            # 清理测试数据
            self._cleanup_test_user(test_username)

    def test_user_not_exists(self) -> None:
        """测试不存在的用户"""
        nonexistent_username = "definitely_does_not_exist_user_12345"

        # 确保用户不存在
        self._cleanup_test_user(nonexistent_username)

        # 检查用户不存在
        assert not has_user(nonexistent_username)

        # 查询不存在的用户应该抛出 ValueError
        with pytest.raises(ValueError, match=f"用户 '{nonexistent_username}' 不存在"):
            get_user(nonexistent_username)

    def _cleanup_test_user(self, username: str) -> None:
        """清理测试用户"""
        try:
            db = SessionLocal()
            try:
                test_user = db.query(UserDB).filter_by(username=username).first()
                if test_user:
                    db.delete(test_user)
                    db.commit()
                    logger.info(f"✅ 测试用户 {username} 清理成功!")
            except Exception as cleanup_error:
                db.rollback()
                logger.error(f"❌ 测试用户 {username} 清理失败: {cleanup_error}")
            finally:
                db.close()

            # 验证清理结果
            user_still_exists = has_user(username)
            if not user_still_exists:
                logger.info(f"✅ 测试用户 {username} 清理验证通过!")
            else:
                logger.warning(f"⚠️ 测试用户 {username} 清理验证异常，用户仍然存在")

        except Exception as e:
            logger.error(f"❌ 清理测试用户 {username} 时发生错误: {e}")

    @pytest.fixture(autouse=True)
    def cleanup_test_users(self) -> Generator[None, None, None]:
        """测试后自动清理测试用户"""
        test_usernames = [
            "test_postgresql_connection",
            "test_crud_user",
            "definitely_does_not_exist_user_12345",
        ]

        yield  # 运行测试

        # 清理所有测试用户
        for username in test_usernames:
            self._cleanup_test_user(username)
