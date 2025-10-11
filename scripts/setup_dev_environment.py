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

import os
from pathlib import Path
import sys
from typing import Final, final

from pydantic import BaseModel

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
from loguru import logger

from ai_rpg.settings import (
    ServerSettings,
)
from ai_rpg.game.config import GLOBAL_GAME_NAME, LOGS_DIR

from ai_rpg.mongodb import (
    BootDocument,
    DungeonDocument,
    DEFAULT_MONGODB_CONFIG,
    mongodb_clear_database,
    mongodb_find_one,
    mongodb_upsert_one,
)
from ai_rpg.pgsql.client import (
    pgsql_ensure_database_tables,
    pgsql_reset_database,
)
from ai_rpg.pgsql.user import has_user, save_user
from ai_rpg.redis.client import (
    redis_flushall,
)
from ai_rpg.demo.world import create_demo_game_world
from ai_rpg.demo.stage_dungeon4 import (
    create_demo_dungeon4,
)


@final
class UserAccount(BaseModel):
    username: str
    hashed_password: str
    display_name: str


FAKE_USER = UserAccount(
    username="yanghangethan@gmail.com",
    hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 明文是 secret
    display_name="yh",
)


#######################################################################################################
def _pgsql_setup_test_user() -> None:
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
        logger.info(f"测试用户 {FAKE_USER.username} 已创建")
    else:
        logger.info(f"测试用户 {FAKE_USER.username} 已存在，跳过创建")


#######################################################################################################
def _mongodb_create_and_store_demo_boot() -> None:
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
                        logger.error("⚠️ 数据完整性验证失败")

                except Exception as validation_error:
                    logger.error(
                        f"❌ WorldBootDocument 便捷方法操作失败: {validation_error}"
                    )
                    logger.info("⚠️ 使用原始字典数据继续验证...")

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
def _mongodb_create_and_store_demo_dungeon() -> None:
    """
    创建演示地下城并存储到 MongoDB

    创建演示地下城数据，并将其存储到 MongoDB 中进行持久化，
    同时验证存储的数据完整性
    """
    logger.info("🚀 创建演示地下城...")
    version = "0.0.1"
    demo_dungeon = create_demo_dungeon4()

    # 存储 demo_dungeon 到 MongoDB
    collection_name = DEFAULT_MONGODB_CONFIG.dungeons_collection  # 地下城集合名称

    try:
        # 创建 DungeonDocument 实例
        dungeon_document = DungeonDocument.create_from_dungeon(
            dungeon=demo_dungeon, version=version
        )

        # 存储到 MongoDB（使用 upsert 语义，如果存在则完全覆盖）
        logger.info(f"📝 存储演示地下城到 MongoDB 集合: {collection_name}")
        inserted_id = mongodb_upsert_one(collection_name, dungeon_document.to_dict())

        if inserted_id:
            logger.success(
                f"✅ 演示地下城已存储到 MongoDB! = \n{dungeon_document.dungeon_data.model_dump_json(indent=2)}"
            )

            # 立即获取验证
            logger.info(f"📖 从 MongoDB 获取演示地下城进行验证...")
            stored_dungeon = mongodb_find_one(
                collection_name, {"dungeon_name": demo_dungeon.name}
            )

            if stored_dungeon:
                try:
                    # 使用便捷方法反序列化为 DungeonDocument 对象
                    stored_document = DungeonDocument.from_mongodb(stored_dungeon)
                    assert (
                        stored_document.dungeon_name == demo_dungeon.name
                    ), "地下城名称不匹配!"
                    logger.success(f"✅ 演示地下城已从 MongoDB 成功获取!")

                except Exception as validation_error:
                    logger.error(
                        f"❌ DungeonDocument 便捷方法操作失败: {validation_error}"
                    )
                    logger.info("⚠️ 使用原始字典数据继续验证...")

                    # 备用验证逻辑（使用原始字典数据）
                    logger.info(f"  - 存储时间: {stored_dungeon['timestamp']}")
                    logger.info(f"  - 版本: {stored_dungeon['version']}")
                    logger.info(
                        f"  - Dungeon 名称: {stored_dungeon['dungeon_data']['name']}"
                    )
                    logger.info(
                        f"  - Dungeon 关卡数量: {len(stored_dungeon['dungeon_data']['stages'])}"
                    )

            else:
                logger.error("❌ 从 MongoDB 获取演示地下城失败!")
        else:
            logger.error("❌ 演示地下城存储到 MongoDB 失败!")

    except Exception as e:
        logger.error(f"❌ 演示地下城 MongoDB 操作失败: {e}")
        raise


#######################################################################################################
def _setup_chromadb_rag_environment() -> None:
    """
    初始化RAG系统

    清理现有的ChromaDB数据，然后使用正式的知识库数据重新初始化RAG系统，
    包括向量数据库的设置和知识库数据的加载
    """
    logger.info("🚀 初始化RAG系统...")

    # 导入必要的模块
    from ai_rpg.chroma import get_default_collection, clear_client
    from ai_rpg.rag import load_knowledge_base_to_vector_db
    from ai_rpg.embedding_model.sentence_transformer import (
        get_embedding_model,
    )
    from ai_rpg.demo.campaign_setting import FANTASY_WORLD_RPG_KNOWLEDGE_BASE

    try:

        # 新的测试
        logger.info("🧹 清空ChromaDB数据库...")
        clear_client()

        # 清理现有的ChromaDB数据

        # chromadb_clear_database()

        # 获取嵌入模型
        embedding_model = get_embedding_model()
        if embedding_model is None:
            logger.error("❌ 嵌入模型初始化失败")
            return

        # 获取ChromaDB实例
        # chroma_db = get_chroma_db()
        # if chroma_db is None or chroma_db.collection is None:
        #     logger.error("❌ ChromaDB实例初始化失败")
        #     return

        # 使用正式知识库数据初始化RAG系统
        logger.info("📚 加载艾尔法尼亚世界知识库...")
        success = load_knowledge_base_to_vector_db(
            FANTASY_WORLD_RPG_KNOWLEDGE_BASE, embedding_model, get_default_collection()
        )

        if success:
            logger.success("✅ RAG系统初始化成功!")
            logger.info(f"  - 知识库类别数量: {len(FANTASY_WORLD_RPG_KNOWLEDGE_BASE)}")

            # 统计总文档数量
            total_documents = sum(
                len(docs) for docs in FANTASY_WORLD_RPG_KNOWLEDGE_BASE.values()
            )
            logger.info(f"  - 总文档数量: {total_documents}")

            # 显示知识库类别
            categories = list(FANTASY_WORLD_RPG_KNOWLEDGE_BASE.keys())
            logger.info(f"  - 知识库类别: {', '.join(categories)}")

        else:
            logger.error("❌ RAG系统初始化失败!")
            raise Exception("RAG系统初始化返回失败状态")

    except ImportError as e:
        logger.error(f"❌ RAG系统模块导入失败: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ RAG系统初始化过程中发生错误: {e}")
        raise


def _generate_pm2_ecosystem_config(
    server_settings: ServerSettings, target_directory: str = "."
) -> None:
    """
    根据 ServerSettings 配置生成 ecosystem.config.js 文件

    Args:
        target_directory: 目标目录路径，默认为当前目录

    确保在项目根目录

    启动所有服务
    pm2 start ecosystem.config.js

    查看状态
    pm2 status

    停止所有服务
    pm2 delete ecosystem.config.js
    """
    ecosystem_config_content = f"""module.exports = {{
  apps: [
    // 聊天服务器实例 - 端口 {server_settings.azure_openai_chat_server_port}
    {{
      name: 'azure-openai-chat-server-{server_settings.azure_openai_chat_server_port}',
      script: 'uvicorn',
      args: 'scripts.run_azure_openai_chat_server:app --host 0.0.0.0 --port {server_settings.azure_openai_chat_server_port}',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {{
        PYTHONPATH: `${{process.cwd()}}`,
        PORT: '{server_settings.azure_openai_chat_server_port}'
      }},
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/azure-openai-chat-server-{server_settings.azure_openai_chat_server_port}.log',
      error_file: './logs/azure-openai-chat-server-{server_settings.azure_openai_chat_server_port}-error.log',
      out_file: './logs/azure-openai-chat-server-{server_settings.azure_openai_chat_server_port}-out.log',
      time: true
    }},
    // 游戏服务器实例 - 端口 {server_settings.game_server_port}
    {{
      name: 'game-server-{server_settings.game_server_port}',
      script: 'uvicorn',
      args: 'scripts.run_tcg_game_server:app --host 0.0.0.0 --port {server_settings.game_server_port}',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {{
        PYTHONPATH: `${{process.cwd()}}`,
        PORT: '{server_settings.game_server_port}'
      }},
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/game-server-{server_settings.game_server_port}.log',
      error_file: './logs/game-server-{server_settings.game_server_port}-error.log',
      out_file: './logs/game-server-{server_settings.game_server_port}-out.log',
      time: true
    }},
    // 图片生成服务器实例 - 端口 {server_settings.image_generation_server_port}
    {{
      name: 'image-generation-server-{server_settings.image_generation_server_port}',
      script: 'uvicorn',
      args: 'scripts.run_image_generation_server:app --host 0.0.0.0 --port {server_settings.image_generation_server_port}',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {{
        PYTHONPATH: `${{process.cwd()}}`,
        PORT: '{server_settings.image_generation_server_port}'
      }},
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/image-generation-server-{server_settings.image_generation_server_port}.log',
      error_file: './logs/image-generation-server-{server_settings.image_generation_server_port}-error.log',
      out_file: './logs/image-generation-server-{server_settings.image_generation_server_port}-out.log',
      time: true
    }},
    // DeepSeek聊天服务器实例 - 端口 {server_settings.deepseek_chat_server_port}
    {{
      name: 'deepseek-chat-server-{server_settings.deepseek_chat_server_port}',
      script: 'uvicorn',
      args: 'scripts.run_deepseek_chat_server:app --host 0.0.0.0 --port {server_settings.deepseek_chat_server_port}',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {{
        PYTHONPATH: `${{process.cwd()}}`,
        PORT: '{server_settings.deepseek_chat_server_port}'
      }},
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/deepseek-chat-server-{server_settings.deepseek_chat_server_port}.log',
      error_file: './logs/deepseek-chat-server-{server_settings.deepseek_chat_server_port}-error.log',
      out_file: './logs/deepseek-chat-server-{server_settings.deepseek_chat_server_port}-out.log',
      time: true
    }}
  ]
}};
"""
    # 确保目标目录存在
    target_path = Path(target_directory)
    target_path.mkdir(parents=True, exist_ok=True)

    # 写入文件
    config_file_path = target_path / "ecosystem.config.js"
    config_file_path.write_text(ecosystem_config_content, encoding="utf-8")

    print(f"已生成 ecosystem.config.js 文件到: {config_file_path.absolute()}")


#######################################################################################################
def _setup_server_settings() -> None:
    """
    构建服务器设置配置
    """
    logger.info("🚀 构建服务器设置配置...")
    # 这里可以添加构建服务器设置配置的逻辑
    server_config: Final[ServerSettings] = ServerSettings()
    write_path = Path("server_settings.json")
    write_path.write_text(server_config.model_dump_json(indent=4), encoding="utf-8")
    logger.success("✅ 服务器设置配置构建完成")

    # 生成PM2生态系统配置
    _generate_pm2_ecosystem_config(server_config)


#######################################################################################################
# Development Environment Setup Utility
def main() -> None:

    logger.info("🚀 开始初始化开发环境...")

    # PostgreSQL 相关操作
    try:
        logger.info("📋 确保数据库表结构...")
        pgsql_ensure_database_tables()
        logger.info("� 清空 PostgreSQL 数据库...")
        pgsql_reset_database()
        logger.info("🚀 设置PostgreSQL测试用户...")
        _pgsql_setup_test_user()
        logger.success("✅ PostgreSQL 初始化完成")
    except Exception as e:
        logger.error(f"❌ PostgreSQL 初始化失败: {e}")

    # Redis 相关操作
    try:
        logger.info("🚀 清空 Redis 数据库...")
        redis_flushall()
        logger.success("✅ Redis 初始化完成")
    except Exception as e:
        logger.error(f"❌ Redis 初始化失败: {e}")

    # MongoDB 相关操作
    try:
        logger.info("🚀 清空 MongoDB 数据库...")
        mongodb_clear_database()
        logger.info("🚀 创建MongoDB演示游戏世界...")
        _mongodb_create_and_store_demo_boot()
        logger.info("🚀 创建MongoDB演示地下城...")
        _mongodb_create_and_store_demo_dungeon()
        logger.success("✅ MongoDB 初始化完成")
    except Exception as e:
        logger.error(f"❌ MongoDB 初始化失败: {e}")

    # RAG 系统相关操作
    try:
        logger.info("🚀 初始化RAG系统...")
        _setup_chromadb_rag_environment()
        logger.success("✅ RAG 系统初始化完成")
    except Exception as e:
        logger.error(f"❌ RAG 系统初始化失败: {e}")

    # 服务器设置相关操作
    try:
        logger.info("🚀 设置服务器配置...")
        _setup_server_settings()
        logger.success("✅ 服务器配置设置完成")
    except Exception as e:
        logger.error(f"❌ 服务器配置设置失败: {e}")

    logger.info("🎉 开发环境初始化完成")


#######################################################################################################
# Main execution
if __name__ == "__main__":
    main()
