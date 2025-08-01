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
from pathlib import Path
import json
import time
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import all required modules at the top
from loguru import logger
from sqlalchemy import text

from multi_agents_game.db.account import FAKE_USER
from multi_agents_game.db.pgsql_client import reset_database, SessionLocal
from multi_agents_game.db.pgsql_object import UserDB
from multi_agents_game.db.pgsql_user import has_user, save_user, get_user
from multi_agents_game.db.redis_client import (
    redis_flushall,
    redis_set,
    redis_get,
    redis_delete,
)
from multi_agents_game.db.mongodb_client import (
    mongodb_clear_database,
    mongodb_insert_one,
    mongodb_upsert_one,
    mongodb_find_one,
    mongodb_update_one,
    mongodb_create_index,
    mongodb_delete_many,
    mongodb_count_documents,
    get_mongodb_database_instance,
)
from multi_agents_game.db.mongodb_boot_document import BootDocument
from multi_agents_game.demo.world import create_demo_game_world
from multi_agents_game.config.game_config import LOGS_DIR, GLOBAL_GAME_NAME
from multi_agents_game.config.db_config import DEFAULT_MONGODB_CONFIG


#######################################################################################################
def _test_redis() -> None:
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
        if retrieved_value == test_value:
            logger.success(f"✅ Redis 连接测试成功! 读取到的值: {retrieved_value}")
        else:
            logger.error(
                f"❌ Redis 连接测试失败! 期望值: {test_value}, 实际值: {retrieved_value}"
            )
            return

        # 清理测试数据
        logger.info(f"🧹 清理测试数据: {test_key}")
        redis_delete(test_key)

        # 验证删除
        deleted_value = redis_get(test_key)
        if deleted_value is None:
            logger.success("✅ 测试数据清理成功!")
        else:
            logger.warning(f"⚠️ 测试数据清理异常，键值仍然存在: {deleted_value}")

        logger.success("🎉 Redis 连接和基本操作测试全部通过!")

    except Exception as e:
        logger.error(f"❌ Redis 连接测试失败: {e}")
        raise


#######################################################################################################
def _test_postgresql() -> None:
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
            if result and result[0] == 1:
                logger.success("✅ PostgreSQL 数据库连接成功!")
            else:
                logger.error("❌ PostgreSQL 数据库连接验证失败!")
                return
        finally:
            db.close()

        # 2. 测试用户创建操作
        logger.info(f"👤 创建测试用户: {test_username}")
        created_user = save_user(
            username=test_username,
            hashed_password=test_password,
            display_name=test_display_name,
        )

        if created_user and created_user.username == test_username:
            logger.success(f"✅ 用户创建成功! 用户ID: {created_user.id}")
        else:
            logger.error("❌ 用户创建失败!")
            return

        # 3. 测试用户查询操作
        logger.info(f"🔍 查询测试用户: {test_username}")
        retrieved_user = get_user(test_username)

        if (
            retrieved_user
            and retrieved_user.username == test_username
            and retrieved_user.hashed_password == test_password
            and retrieved_user.display_name == test_display_name
        ):
            logger.success(f"✅ 用户查询成功! 显示名: {retrieved_user.display_name}")
        else:
            logger.error("❌ 用户查询失败或数据不匹配!")
            return

        # 4. 测试用户存在性检查
        logger.info(f"🔎 检查用户是否存在: {test_username}")
        user_exists = has_user(test_username)

        if user_exists:
            logger.success("✅ 用户存在性检查通过!")
        else:
            logger.error("❌ 用户存在性检查失败!")
            return

        # 5. 清理测试数据
        logger.info(f"🧹 清理测试数据: {test_username}")
        db = SessionLocal()
        try:
            test_user = db.query(UserDB).filter_by(username=test_username).first()
            if test_user:
                db.delete(test_user)
                db.commit()
                logger.success("✅ 测试数据清理成功!")
            else:
                logger.warning("⚠️ 未找到要清理的测试用户")
        except Exception as cleanup_error:
            db.rollback()
            logger.error(f"❌ 测试数据清理失败: {cleanup_error}")
        finally:
            db.close()

        # 6. 验证清理结果
        logger.info(f"🔍 验证测试数据已清理: {test_username}")
        user_still_exists = has_user(test_username)

        if not user_still_exists:
            logger.success("✅ 测试数据清理验证通过!")
        else:
            logger.warning("⚠️ 测试数据清理验证异常，用户仍然存在")

        logger.success("🎉 PostgreSQL 连接和基本操作测试全部通过!")

    except Exception as e:
        logger.error(f"❌ PostgreSQL 连接测试失败: {e}")
        raise


#######################################################################################################
def _test_mongodb() -> None:
    """
    测试 MongoDB 连接和基本操作

    使用模拟的 World 对象数据验证 MongoDB 连接的可用性
    包括：连接测试、文档插入、查询、更新、索引创建和清理操作
    """
    collection_name = "test_worlds"
    test_game_id = "game_123"

    try:
        logger.info("🔍 开始测试 MongoDB 连接...")

        # 1. 测试数据库连接
        logger.info("📡 测试 MongoDB 数据库连接...")
        try:
            db = get_mongodb_database_instance()
            # 测试连接 - 通过列出集合来验证连接
            collections = db.list_collection_names()
            logger.success(
                f"✅ MongoDB 数据库连接成功! 当前集合数量: {len(collections)}"
            )
        except Exception as e:
            logger.error(f"❌ MongoDB 数据库连接失败: {e}")
            return

        # 2. 测试 World 对象存储
        logger.info("🌍 测试 World 对象存储...")

        # 模拟 World 类数据
        world_data = {
            "_id": "game_123_runtime_1001",
            "game_id": test_game_id,
            "runtime_index": 1001,
            "version": "0.0.1",
            "timestamp": datetime.now(),
            "entities_snapshot": [
                {
                    "entity_id": "player_1",
                    "type": "player",
                    "name": "张三",
                    "level": 5,
                    "hp": 100,
                    "position": {"x": 10, "y": 20},
                },
                {
                    "entity_id": "monster_1",
                    "type": "monster",
                    "name": "哥布林",
                    "level": 3,
                    "hp": 50,
                    "position": {"x": 15, "y": 25},
                },
            ],
            "agents_short_term_memory": {
                "player_1": {
                    "name": "张三",
                    "chat_history": [
                        {
                            "type": "human",
                            "content": "我想攻击哥布林",
                            "timestamp": datetime.now(),
                        },
                        {
                            "type": "ai",
                            "content": "你攻击了哥布林，造成了10点伤害",
                            "timestamp": datetime.now(),
                        },
                    ],
                }
            },
            "dungeon": {
                "name": "新手村地牢",
                "level": 1,
                "monsters_count": 5,
                "treasure_chests": 2,
            },
            "boot": {
                "name": "游戏启动配置",
                "campaign_setting": "奇幻世界",
                "stages": ["新手村", "森林", "城堡"],
                "world_systems": ["战斗系统", "经验系统", "装备系统"],
            },
        }

        # 插入 World 数据
        logger.info(f"📝 插入 World 数据到集合: {collection_name}")
        inserted_id = mongodb_insert_one(collection_name, world_data)

        if inserted_id:
            logger.success(f"✅ World 数据插入成功, ID: {inserted_id}")
        else:
            logger.error("❌ World 数据插入失败!")
            return

        # 查询 World 数据
        logger.info(f"📖 查询 World 数据: game_id = {test_game_id}")
        stored_world = mongodb_find_one(collection_name, {"game_id": test_game_id})

        if stored_world:
            logger.success("✅ World 数据查询成功!")
            logger.info(f"  - 游戏ID: {stored_world['game_id']}")
            logger.info(f"  - 运行时索引: {stored_world['runtime_index']}")
            logger.info(f"  - 实体数量: {len(stored_world['entities_snapshot'])}")
            logger.info(
                f"  - 智能体数量: {len(stored_world['agents_short_term_memory'])}"
            )
            logger.info(f"  - 地牢名称: {stored_world['dungeon']['name']}")

            # 计算存储大小
            json_str = json.dumps(stored_world, default=str)
            size_mb = len(json_str.encode("utf-8")) / (1024 * 1024)
            logger.info(f"  - 文档大小: {size_mb:.3f} MB")
        else:
            logger.error("❌ World 数据查询失败!")
            return

        # 3. 测试增量更新
        logger.info("🔄 测试增量更新...")

        update_result = mongodb_update_one(
            collection_name,
            {"game_id": test_game_id},
            {
                "$inc": {"runtime_index": 1},
                "$set": {"last_updated": datetime.now()},
                "$push": {
                    "entities_snapshot": {
                        "entity_id": "npc_1",
                        "type": "npc",
                        "name": "村长",
                        "level": 10,
                        "position": {"x": 5, "y": 5},
                    }
                },
            },
        )

        if update_result:
            logger.success("✅ 增量更新成功!")

            # 查看更新后的数据
            updated_world = mongodb_find_one(collection_name, {"game_id": test_game_id})
            if updated_world:
                logger.info(f"  - 新的运行时索引: {updated_world['runtime_index']}")
                logger.info(f"  - 实体数量: {len(updated_world['entities_snapshot'])}")
            else:
                logger.warning("  - 无法获取更新后的数据")
        else:
            logger.error("❌ 增量更新失败!")
            return

        # 4. 测试查询性能和索引创建
        logger.info("⚡ 测试查询性能和索引创建...")

        # 创建索引
        try:
            index_name = mongodb_create_index(
                collection_name, [("game_id", 1), ("runtime_index", -1)]
            )
            logger.success(f"✅ 创建索引成功: {index_name}")
        except Exception as e:
            logger.warning(f"⚠️ 索引创建失败或已存在: {e}")

        # 测试查询速度
        start_time = time.time()

        # 查询最新的游戏状态（模拟按索引查询）
        latest_world = mongodb_find_one(collection_name, {"game_id": test_game_id})

        end_time = time.time()
        query_time = (end_time - start_time) * 1000  # 转换为毫秒

        if latest_world:
            logger.success("✅ 查询性能测试完成")
            logger.info(f"  - 查询时间: {query_time:.2f} ms")
            logger.info(f"  - 最新运行时索引: {latest_world['runtime_index']}")
        else:
            logger.error("❌ 查询性能测试失败!")
            return

        # 5. 统计文档数量
        logger.info("📊 统计测试文档数量...")
        doc_count = mongodb_count_documents(collection_name, {"game_id": test_game_id})
        logger.info(f"  - 测试文档数量: {doc_count}")

        # 6. 清理测试数据
        logger.info("🧹 清理测试数据...")
        deleted_count = mongodb_delete_many(collection_name, {"game_id": test_game_id})

        if deleted_count > 0:
            logger.success(f"✅ 测试数据清理成功，删除了 {deleted_count} 条记录")
        else:
            logger.warning("⚠️ 未找到要清理的测试数据")

        # 7. 验证清理结果
        logger.info("🔍 验证测试数据已清理...")
        remaining_count = mongodb_count_documents(
            collection_name, {"game_id": test_game_id}
        )

        if remaining_count == 0:
            logger.success("✅ 测试数据清理验证通过!")
        else:
            logger.warning(f"⚠️ 测试数据清理验证异常，仍有 {remaining_count} 条记录")

        logger.success("🎉 MongoDB 连接和基本操作测试全部通过!")
        logger.info("💡 MongoDB 使用建议:")
        logger.info("  1. 为游戏ID和运行时索引创建复合索引")
        logger.info("  2. 考虑定期归档旧的游戏状态")
        logger.info("  3. 监控文档大小，避免超过16MB限制")
        logger.info("  4. 使用批量操作提高写入性能")
        logger.info("  5. 考虑数据压缩和分片策略")

    except Exception as e:
        logger.error(f"❌ MongoDB 连接测试失败: {e}")
        raise


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
    # 第一阶段：数据库连接测试
    logger.info("🚀 首先测试 Redis 连接...")
    _test_redis()

    logger.info("🚀 测试 PostgreSQL 连接...")
    _test_postgresql()

    logger.info("🚀 测试 MongoDB 连接...")
    _test_mongodb()

    # 第二阶段：清空所有数据库
    logger.info("🚀 清空 Redis 数据库...")
    redis_flushall()

    logger.info("🚀 清空 PostgreSQL 数据库...")
    reset_database()

    logger.info("🚀 清空 MongoDB 数据库...")
    mongodb_clear_database()

    # 第三阶段：初始化开发环境
    _setup_test_user()
    _create_and_store_demo_world()


#######################################################################################################
# Main execution
if __name__ == "__main__":
    main()
