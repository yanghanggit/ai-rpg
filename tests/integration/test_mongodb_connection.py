#!/usr/bin/env python3
"""
MongoDB 连接和基本操作测试

测试 MongoDB 连接的可用性和基本文档操作
包括：连接测试、文档插入、查询、更新、索引创建、性能测试和清理操作

Author: yanghanggit
Date: 2025-08-01
"""

from typing import Generator, Dict, Any, Optional
import pytest
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from loguru import logger

# 添加 src 目录到 Python 路径
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from multi_agents_game.db.mongodb_client import (
    mongodb_insert_one,
    mongodb_upsert_one,
    mongodb_find_one,
    mongodb_update_one,
    mongodb_create_index,
    mongodb_delete_many,
    mongodb_count_documents,
    get_mongodb_database_instance,
)


class TestMongoDBConnection:
    """MongoDB 连接和基本操作测试类"""

    def test_mongodb_connection_and_operations(self) -> None:
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
                raise

            # 2. 测试 World 对象存储
            logger.info("🌍 测试 World 对象存储...")

            # 模拟 World 类数据
            world_data = self._create_test_world_data(test_game_id)

            # 插入 World 数据
            logger.info(f"📝 插入 World 数据到集合: {collection_name}")
            inserted_id = mongodb_insert_one(collection_name, world_data)

            assert inserted_id, "World 数据插入失败!"
            logger.success(f"✅ World 数据插入成功, ID: {inserted_id}")

            # 查询 World 数据
            logger.info(f"📖 查询 World 数据: game_id = {test_game_id}")
            stored_world = mongodb_find_one(collection_name, {"game_id": test_game_id})

            assert stored_world, "World 数据查询失败!"
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

            assert update_result, "增量更新失败!"
            logger.success("✅ 增量更新成功!")

            # 查看更新后的数据
            updated_world = mongodb_find_one(collection_name, {"game_id": test_game_id})
            if updated_world:
                logger.info(f"  - 新的运行时索引: {updated_world['runtime_index']}")
                logger.info(f"  - 实体数量: {len(updated_world['entities_snapshot'])}")

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

            assert latest_world, "查询性能测试失败!"
            logger.success("✅ 查询性能测试完成")
            logger.info(f"  - 查询时间: {query_time:.2f} ms")
            logger.info(f"  - 最新运行时索引: {latest_world['runtime_index']}")

            # 5. 统计文档数量
            logger.info("📊 统计测试文档数量...")
            doc_count = mongodb_count_documents(
                collection_name, {"game_id": test_game_id}
            )
            logger.info(f"  - 测试文档数量: {doc_count}")

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
        finally:
            # 6. 清理测试数据
            logger.info("🧹 清理测试数据...")
            self._cleanup_test_data(collection_name, test_game_id)

    def test_database_connection(self) -> None:
        """测试 MongoDB 数据库连接"""
        try:
            db = get_mongodb_database_instance()
            collections = db.list_collection_names()
            logger.info(f"✅ MongoDB 连接测试通过，集合数量: {len(collections)}")
        except Exception as e:
            logger.error(f"❌ MongoDB 连接失败: {e}")
            raise

    def test_document_crud_operations(self) -> None:
        """测试文档 CRUD 操作"""
        collection_name = "test_crud_collection"
        test_game_id = "test_crud_game"

        try:
            # 创建测试文档
            test_doc = {
                "_id": f"{test_game_id}_test",
                "game_id": test_game_id,
                "name": "Test Document",
                "value": 42,
                "timestamp": datetime.now(),
            }

            # 插入文档
            inserted_id = mongodb_insert_one(collection_name, test_doc)
            assert inserted_id is not None

            # 查询文档
            found_doc = mongodb_find_one(collection_name, {"game_id": test_game_id})
            assert found_doc is not None
            assert found_doc["game_id"] == test_game_id
            assert found_doc["name"] == "Test Document"
            assert found_doc["value"] == 42

            # 更新文档
            update_result = mongodb_update_one(
                collection_name,
                {"game_id": test_game_id},
                {"$set": {"value": 100, "updated": True}},
            )
            assert update_result

            # 验证更新
            updated_doc = mongodb_find_one(collection_name, {"game_id": test_game_id})
            assert updated_doc is not None
            assert updated_doc["value"] == 100
            assert updated_doc["updated"] is True

            # 统计文档数量
            count = mongodb_count_documents(collection_name, {"game_id": test_game_id})
            assert count == 1

            logger.info("✅ 文档 CRUD 操作测试通过")

        finally:
            # 清理测试数据
            self._cleanup_test_data(collection_name, test_game_id)

    def test_upsert_operation(self) -> None:
        """测试 upsert 操作"""
        collection_name = "test_upsert_collection"
        test_game_id = "test_upsert_game"

        try:
            # 第一次 upsert（插入）
            test_doc = {
                "_id": f"{test_game_id}_upsert",
                "game_id": test_game_id,
                "version": 1,
            }

            result1 = mongodb_upsert_one(collection_name, test_doc)
            assert result1 is not None

            # 第二次 upsert（更新）
            updated_doc = {
                "_id": f"{test_game_id}_upsert",
                "game_id": test_game_id,
                "version": 2,
            }

            result2 = mongodb_upsert_one(collection_name, updated_doc)
            assert result2 is not None

            # 验证只有一个文档且版本为2
            count = mongodb_count_documents(collection_name, {"game_id": test_game_id})
            assert count == 1

            found_doc = mongodb_find_one(collection_name, {"game_id": test_game_id})
            assert found_doc is not None
            assert found_doc["version"] == 2

            logger.info("✅ Upsert 操作测试通过")

        finally:
            # 清理测试数据
            self._cleanup_test_data(collection_name, test_game_id)

    def _create_test_world_data(self, test_game_id: str) -> Dict[str, Any]:
        """创建测试世界数据"""
        return {
            "_id": f"{test_game_id}_runtime_1001",
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

    def _cleanup_test_data(self, collection_name: str, test_game_id: str) -> None:
        """清理测试数据"""
        try:
            deleted_count = mongodb_delete_many(
                collection_name, {"game_id": test_game_id}
            )

            if deleted_count > 0:
                logger.success(f"✅ 测试数据清理成功，删除了 {deleted_count} 条记录")
            else:
                logger.info("📝 未找到要清理的测试数据")

            # 验证清理结果
            remaining_count = mongodb_count_documents(
                collection_name, {"game_id": test_game_id}
            )

            if remaining_count == 0:
                logger.success("✅ 测试数据清理验证通过!")
            else:
                logger.warning(f"⚠️ 测试数据清理验证异常，仍有 {remaining_count} 条记录")

        except Exception as e:
            logger.error(f"❌ 清理测试数据时发生错误: {e}")

    @pytest.fixture(autouse=True)
    def cleanup_test_collections(self) -> Generator[None, None, None]:
        """测试后自动清理测试集合"""
        test_collections_and_games = [
            ("test_worlds", "game_123"),
            ("test_crud_collection", "test_crud_game"),
            ("test_upsert_collection", "test_upsert_game"),
        ]

        yield  # 运行测试

        # 清理所有测试数据
        for collection_name, game_id in test_collections_and_games:
            self._cleanup_test_data(collection_name, game_id)
