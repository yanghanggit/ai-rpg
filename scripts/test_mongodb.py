#!/usr/bin/env python3
"""
MongoDB 连接测试脚本
测试 MongoDB 的基本操作，包括连接、插入、查询等
"""

import pymongo
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
import json


def test_mongodb_connection() -> Tuple[
    Optional[pymongo.MongoClient[Dict[str, Any]]],
    Optional[pymongo.database.Database[Dict[str, Any]]],
    Optional[pymongo.collection.Collection[Dict[str, Any]]],
    Optional[pymongo.collection.Collection[Dict[str, Any]]],
]:
    """测试 MongoDB 连接"""
    try:
        # 连接到 MongoDB
        client: pymongo.MongoClient[Dict[str, Any]] = pymongo.MongoClient(
            "mongodb://localhost:27017/"
        )

        # 测试连接
        client.admin.command("ping")
        print("✅ MongoDB 连接成功!")

        # 获取数据库
        db = client["multi_agents_game"]

        # 获取集合（类似于关系数据库中的表）
        worlds_collection = db["worlds"]
        players_collection = db["players"]

        print(f"📊 数据库: {db.name}")
        print(f"📋 可用集合: {db.list_collection_names()}")

        return client, db, worlds_collection, players_collection

    except Exception as e:
        print(f"❌ MongoDB 连接失败: {e}")
        return None, None, None, None


def test_world_storage(
    worlds_collection: pymongo.collection.Collection[Dict[str, Any]]
) -> bool:
    """测试 World 对象存储"""
    print("\n" + "=" * 50)
    print("🌍 测试 World 对象存储")
    print("=" * 50)

    # 模拟你的 World 类数据
    world_data = {
        "_id": "game_123_runtime_1001",
        "game_id": "game_123",
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

    try:
        # 插入 World 数据
        result = worlds_collection.insert_one(world_data)
        print(f"✅ World 数据插入成功, ID: {result.inserted_id}")

        # 查询数据
        stored_world = worlds_collection.find_one({"game_id": "game_123"})

        if stored_world:
            print(f"📖 存储的 World 数据:")
            print(f"  - 游戏ID: {stored_world['game_id']}")
            print(f"  - 运行时索引: {stored_world['runtime_index']}")
            print(f"  - 实体数量: {len(stored_world['entities_snapshot'])}")
            print(f"  - 智能体数量: {len(stored_world['agents_short_term_memory'])}")
            print(f"  - 地牢名称: {stored_world['dungeon']['name']}")

            # 计算存储大小
            json_str = json.dumps(stored_world, default=str)
            size_mb = len(json_str.encode("utf-8")) / (1024 * 1024)
            print(f"  - 文档大小: {size_mb:.3f} MB")

        return True

    except Exception as e:
        print(f"❌ World 数据操作失败: {e}")
        return False


def test_incremental_updates(
    worlds_collection: pymongo.collection.Collection[Dict[str, Any]]
) -> bool:
    """测试增量更新"""
    print("\n" + "=" * 50)
    print("🔄 测试增量更新")
    print("=" * 50)

    try:
        # 更新运行时索引
        result = worlds_collection.update_one(
            {"game_id": "game_123"},
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

        if result.modified_count > 0:
            print("✅ 增量更新成功")

            # 查看更新后的数据
            updated_world = worlds_collection.find_one({"game_id": "game_123"})
            if updated_world is not None:
                print(f"  - 新的运行时索引: {updated_world['runtime_index']}")
                print(f"  - 实体数量: {len(updated_world['entities_snapshot'])}")
            else:
                print("  - 无法获取更新后的数据")

        return True

    except Exception as e:
        print(f"❌ 增量更新失败: {e}")
        return False


def test_query_performance(
    worlds_collection: pymongo.collection.Collection[Dict[str, Any]]
) -> bool:
    """测试查询性能"""
    print("\n" + "=" * 50)
    print("⚡ 测试查询性能")
    print("=" * 50)

    try:
        import time

        # 创建索引
        worlds_collection.create_index([("game_id", 1), ("runtime_index", -1)])
        print("✅ 创建索引成功")

        # 测试查询速度
        start_time = time.time()

        # 查询最新的游戏状态
        latest_world = worlds_collection.find_one(
            {"game_id": "game_123"}, sort=[("runtime_index", -1)]
        )

        end_time = time.time()
        query_time = (end_time - start_time) * 1000  # 转换为毫秒

        print(f"✅ 查询完成")
        print(f"  - 查询时间: {query_time:.2f} ms")
        if latest_world is not None:
            print(f"  - 最新运行时索引: {latest_world['runtime_index']}")
        else:
            print("  - 无法获取查询结果")

        return True

    except Exception as e:
        print(f"❌ 查询性能测试失败: {e}")
        return False


def test_cleanup(
    worlds_collection: pymongo.collection.Collection[Dict[str, Any]]
) -> bool:
    """清理测试数据"""
    print("\n" + "=" * 50)
    print("🧹 清理测试数据")
    print("=" * 50)

    try:
        result = worlds_collection.delete_many({"game_id": "game_123"})
        print(f"✅ 清理完成，删除了 {result.deleted_count} 条记录")
        return True

    except Exception as e:
        print(f"❌ 清理失败: {e}")
        return False


def main() -> None:
    """主函数"""
    print("🚀 MongoDB 功能测试")
    print("=" * 50)

    # 连接 MongoDB
    client, db, worlds_collection, players_collection = test_mongodb_connection()

    if not client or worlds_collection is None:
        return

    try:
        # 运行测试
        test_world_storage(worlds_collection)
        test_incremental_updates(worlds_collection)
        test_query_performance(worlds_collection)

        # 询问是否清理测试数据
        cleanup = input("\n是否清理测试数据? (y/n): ").lower().strip()
        if cleanup == "y":
            test_cleanup(worlds_collection)

        print("\n✅ 所有测试完成!")
        print("\n💡 MongoDB 使用建议:")
        print("  1. 为游戏ID和运行时索引创建复合索引")
        print("  2. 考虑定期归档旧的游戏状态")
        print("  3. 监控文档大小，避免超过16MB限制")
        print("  4. 使用批量操作提高写入性能")
        print("  5. 考虑数据压缩和分片策略")

    finally:
        # 关闭连接
        client.close()
        print("\n🔌 MongoDB 连接已关闭")


if __name__ == "__main__":
    main()
