#!/usr/bin/env python3
"""
Development Environment Setup Script

This script sets up and initializes the development environment for the multi-agents game framework.

Main functions:
1. Test database connections (Redis, PostgreSQL, MongoDB)
2. Clear and reset all databases
3. Initialize development environment with test data
4. Create and store demo game world

Usage:
    python setup_dev_environment.py

Author: yanghanggit
Date: 2025-07-30
"""

import sys
import os

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

# from pathlib import Path

# Import all required modules at the top
from loguru import logger
from multi_agents_game.db.account import FAKE_USER

# from multi_agents_game.db.pgsql_client import reset_database, ensure_database_tables
from multi_agents_game.db.pgsql_user import has_user, save_user
from multi_agents_game.db.redis_client import (
    redis_flushall,
)
from multi_agents_game.db.mongodb_client import (
    mongodb_clear_database,
    mongodb_upsert_one,
    mongodb_find_one,
)
from multi_agents_game.db.mongodb_boot_document import BootDocument
from multi_agents_game.demo.world import create_demo_game_world
from multi_agents_game.config import (
    LOGS_DIR,
    GLOBAL_GAME_NAME,
    DEFAULT_MONGODB_CONFIG,
)


#######################################################################################################
def _setup_test_user() -> None:
    """
    检查并保存测试用户

    如果测试用户不存在，则创建一个用于开发测试的用户账号
    """
    logger.info("🚀 检查并保存测试用户...")
    if not has_user(FAKE_USER.username):
        save_user(
            username=FAKE_USER.username,
            hashed_password=FAKE_USER.hashed_password,
            display_name=FAKE_USER.display_name,
        )
        logger.warning(f"测试用户 {FAKE_USER.username} 已创建")
    else:
        logger.info(f"测试用户 {FAKE_USER.username} 已存在，跳过创建")


#######################################################################################################
def _create_and_store_demo_world() -> None:
    """
    创建演示游戏世界并存储到 MongoDB

    创建演示游戏世界的启动配置，并将其存储到 MongoDB 中进行持久化，
    同时验证存储的数据完整性
    """
    logger.info("🚀 创建演示游戏世界...")
    game_name = GLOBAL_GAME_NAME
    version = "0.0.1"
    world_boot = create_demo_game_world(game_name)

    # 存储 world_boot 到 MongoDB
    collection_name = DEFAULT_MONGODB_CONFIG.worlds_boot_collection

    try:
        # 创建 WorldBootDocument 实例
        world_boot_document = BootDocument.create_from_boot(
            boot=world_boot, version=version
        )

        # 存储到 MongoDB（使用 upsert 语义，如果存在则完全覆盖）
        logger.info(f"📝 存储演示游戏世界到 MongoDB 集合: {collection_name}")
        inserted_id = mongodb_upsert_one(collection_name, world_boot_document.to_dict())

        if inserted_id:
            logger.success(f"✅ 演示游戏世界已存储到 MongoDB!")
            logger.info(f"  - 游戏名称: {game_name}")
            logger.info(f"  - 集合名称: {collection_name}")
            logger.info(f"  - 文档ID: {world_boot_document.document_id}")
            logger.info(f"  - 场景数量: {world_boot_document.stages_count}")
            logger.info(f"  - 角色数量: {world_boot_document.actors_count}")
            logger.info(f"  - 世界系统数量: {world_boot_document.world_systems_count}")
            logger.info(f"  - 战役设置: {world_boot.campaign_setting}")

            # 立即获取验证
            logger.info(f"📖 从 MongoDB 获取演示游戏世界进行验证...")
            stored_boot = mongodb_find_one(collection_name, {"game_name": game_name})

            if stored_boot:
                try:
                    # 使用便捷方法反序列化为 WorldBootDocument 对象
                    stored_document = BootDocument.from_mongodb(stored_boot)

                    logger.success(f"✅ 演示游戏世界已从 MongoDB 成功获取!")

                    # 使用便捷方法获取摘要信息
                    summary = stored_document.get_summary()
                    logger.info(f"  - 文档摘要:")
                    for key, value in summary.items():
                        logger.info(f"    {key}: {value}")

                    # 验证数据完整性
                    if stored_document.validate_integrity():
                        logger.success("✅ 数据完整性验证通过!")

                        # 使用便捷方法保存 Boot 配置文件
                        # 使用Windows兼容的时间戳格式
                        timestamp_str = stored_document.timestamp.strftime(
                            "%Y-%m-%d_%H-%M-%S"
                        )
                        boot_file_path = (
                            LOGS_DIR
                            / f"boot-{stored_document.boot_data.name}-{timestamp_str}.json"
                        )
                        saved_path = stored_document.save_boot_to_file(boot_file_path)
                        logger.info(f"  - 世界启动配置已保存到: {saved_path}")

                    else:
                        logger.warning("⚠️ 数据完整性验证失败")

                except Exception as validation_error:
                    logger.error(
                        f"❌ WorldBootDocument 便捷方法操作失败: {validation_error}"
                    )
                    logger.warning("⚠️ 使用原始字典数据继续验证...")

                    # 备用验证逻辑（使用原始字典数据）
                    logger.info(f"  - 存储时间: {stored_boot['timestamp']}")
                    logger.info(f"  - 版本: {stored_boot['version']}")
                    logger.info(f"  - Boot 名称: {stored_boot['boot_data']['name']}")
                    logger.info(
                        f"  - Boot 场景数量: {len(stored_boot['boot_data']['stages'])}"
                    )

            else:
                logger.error("❌ 从 MongoDB 获取演示游戏世界失败!")
        else:
            logger.error("❌ 演示游戏世界存储到 MongoDB 失败!")

    except Exception as e:
        logger.error(f"❌ 演示游戏世界 MongoDB 操作失败: {e}")
        raise


#######################################################################################################
# Development Environment Setup Utility
def main() -> None:

    logger.info("🚀 开始初始化开发环境...")

    # 首先确保数据库表结构存在
    logger.info("📋 确保数据库表结构...")
    # try:
    #     ensure_database_tables()
    #     logger.success("✅ 数据库表结构检查完成")
    # except Exception as e:
    #     logger.error(f"❌ 数据库连接失败: {e}")
    #     logger.info("💡 请检查PostgreSQL是否运行，以及用户权限配置")
    #     raise

    # 第1阶段：清空所有数据库
    logger.info("🚀 清空 Redis 数据库...")
    redis_flushall()

    # logger.info("🚀 清空 PostgreSQL 数据库...")
    # reset_database()

    logger.info("🚀 清空 MongoDB 数据库...")
    mongodb_clear_database()

    # 第2阶段：初始化开发环境
    _setup_test_user()
    _create_and_store_demo_world()


#######################################################################################################
# Main execution
if __name__ == "__main__":
    main()
