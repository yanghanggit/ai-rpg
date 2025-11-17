"""
World 相关的 MongoDB 文档模型和存储操作
"""

from datetime import datetime
from typing import final
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from loguru import logger
from ..models.world import World
from .agent_document import save_agent_contexts, load_agent_contexts
from .entity_document import save_entity_serializations, load_entity_serializations
from .boot_document import save_boot, load_boot
from .dungeon_document import save_dungeon, load_dungeon
from .client import (
    mongo_upsert_one,
    mongo_find_one,
    mongo_delete_one,
    mongo_delete_many,
)


###############################################################################################################################################
@final
class WorldDocument(BaseModel):
    """
    MongoDB 文档模型：游戏世界启动配置

    用于存储游戏世界的启动配置信息到 MongoDB 中，包含游戏名称、时间戳、版本和启动数据。
    """

    # Pydantic V2 配置
    model_config = ConfigDict(
        populate_by_name=True,  # 允许使用字段别名（如 _id）
        arbitrary_types_allowed=True,  # 允许任意类型（如果需要）
    )

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="_id",
        description="文档唯一标识符，使用 UUID",
    )
    username: str = Field(..., description="用户名")
    game_name: str = Field(..., description="游戏名称")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间戳")
    version: str = Field(default="1.0.0", description="版本号")
    runtime_index: int = Field(default=1000, description="运行时索引计数器")
    boot_id: str = Field(default="", description="关联的 Boot 文档 ID")
    dungeon_id: str = Field(default="", description="关联的 Dungeon 文档 ID")


###############################################################################################################################################
def save_world(username: str, world: World) -> str:
    """
    存储完整的 World 对象到 MongoDB

    参数:
        username: 用户名
        world: World 对象

    返回:
        str: World 文档的 ID

    说明:
        - 创建 WorldDocument 并生成唯一 ID
        - 调用 save_world_agent_contexts 存储所有 AgentContext
        - 后续会添加其他 World 数据的存储（entities_serialization, dungeon, boot）
    """
    try:
        # 创建 WorldDocument (id 会自动生成)
        world_doc = WorldDocument(
            username=username,
            game_name=world.boot.name,  # 使用 boot.name 作为游戏名称
            runtime_index=world.runtime_index,  # 存储运行时索引
        )

        # 获取生成的 world_id
        world_id = world_doc.id

        # 存储 WorldDocument
        doc_dict = world_doc.model_dump(by_alias=True)
        result_id = mongo_upsert_one("worlds", doc_dict, filter_key="_id")

        if not result_id:
            raise RuntimeError(f"存储 WorldDocument 失败")

        logger.info(
            f"存储 WorldDocument 成功: ID={world_id}, game_name={world.boot.name}"
        )

        # 存储 AgentContexts
        saved_context_ids = save_agent_contexts(world.agents_context, world_id)
        logger.info(f"存储 {len(saved_context_ids)} 个 AgentContext")

        # 存储 EntitySerializations
        saved_entity_ids = save_entity_serializations(
            world.entities_serialization, world_id
        )
        logger.info(f"存储 {len(saved_entity_ids)} 个 EntitySerialization")

        # 存储 Boot (如果有效)
        boot_id = save_boot(world.boot, world_id)
        if boot_id:
            # 更新 WorldDocument 的 boot_id
            world_doc.boot_id = boot_id
            doc_dict = world_doc.model_dump(by_alias=True)
            mongo_upsert_one("worlds", doc_dict, filter_key="_id")
            logger.info(f"存储 Boot: ID={boot_id}")

        # 存储 Dungeon (每次都保存，因为是运行时数据)
        dungeon_id = save_dungeon(world.dungeon, world_id)
        if dungeon_id:
            # 更新 WorldDocument 的 dungeon_id
            world_doc.dungeon_id = dungeon_id
            doc_dict = world_doc.model_dump(by_alias=True)
            mongo_upsert_one("worlds", doc_dict, filter_key="_id")
            logger.info(f"存储 Dungeon: ID={dungeon_id}")

        logger.info(f"World 存储完成: ID={world_id}")
        return world_id

    except Exception as e:
        logger.error(f"存储 World 失败: {e}")
        raise


###############################################################################################################################################
def load_world(world_id: str) -> World:
    """
    从 MongoDB 加载完整的 World 对象

    参数:
        world_id: World 文档的 ID

    返回:
        World: 还原的 World 对象（目前只还原 agents_context）

    说明:
        - 从 worlds 集合加载 WorldDocument
        - 加载 agents_context（消息内容暂未实现）
        - 创建一个不完整的 World 对象（boot, dungeon, entities_serialization 为默认值）
        - TODO: 后续添加完整的数据还原
    """
    try:
        # 加载 WorldDocument
        world_doc_dict = mongo_find_one("worlds", filter_dict={"_id": world_id})

        if not world_doc_dict:
            raise ValueError(f"未找到 World 文档: {world_id}")

        logger.info(
            f"加载 WorldDocument: ID={world_id}, game_name={world_doc_dict.get('game_name')}"
        )

        # 加载 AgentContexts
        agents_context = load_agent_contexts(world_id)

        # 加载 EntitySerializations
        entities_serialization = load_entity_serializations(world_id)

        # 加载 Boot
        boot = load_boot(world_id)

        # 加载 Dungeon
        dungeon = load_dungeon(world_id)

        # 创建 World 对象
        world = World(
            runtime_index=world_doc_dict.get("runtime_index", 1000),  # 加载运行时索引
            agents_context=agents_context,
            entities_serialization=entities_serialization,  # 加载实体序列化
            boot=boot,  # 加载 Boot
            dungeon=dungeon,  # 加载 Dungeon
        )

        logger.info(f"World 加载完成: ID={world_id}")
        return world

    except Exception as e:
        logger.error(f"加载 World 失败: {e}")
        raise


###############################################################################################################################################
def delete_world(world_id: str) -> bool:
    """
    从 MongoDB 删除完整的 World 对象及其所有关联数据

    参数:
        world_id: World 文档的 ID

    返回:
        bool: 是否成功删除

    说明:
        - 删除 WorldDocument
        - 删除所有关联的 AgentContext (agent_contexts 集合)
        - 删除所有关联的 AgentMessage (agent_messages 集合)
        - 删除所有关联的 EntitySerialization (entity_serializations 集合)
        - 删除所有关联的 EntityComponent (entity_components 集合)
        - 级联删除所有子数据
    """
    try:
        # 检查 World 是否存在
        world_doc = mongo_find_one("worlds", filter_dict={"_id": world_id})
        if not world_doc:
            logger.warning(f"World 不存在: {world_id}")
            return False

        logger.info(
            f"开始删除 World: ID={world_id}, game_name={world_doc.get('game_name')}"
        )

        # 删除 AgentContexts
        deleted_agent_contexts = mongo_delete_many(
            "agent_contexts", filter_dict={"world_id": world_id}
        )
        logger.info(f"删除 {deleted_agent_contexts} 个 AgentContext")

        # 删除 AgentMessages
        deleted_agent_messages = mongo_delete_many(
            "agent_messages", filter_dict={"world_id": world_id}
        )
        logger.info(f"删除 {deleted_agent_messages} 个 AgentMessage")

        # 删除 EntitySerializations
        deleted_entity_serializations = mongo_delete_many(
            "entity_serializations", filter_dict={"world_id": world_id}
        )
        logger.info(f"删除 {deleted_entity_serializations} 个 EntitySerialization")

        # 删除 EntityComponents
        deleted_entity_components = mongo_delete_many(
            "entity_components", filter_dict={"world_id": world_id}
        )
        logger.info(f"删除 {deleted_entity_components} 个 EntityComponent")

        # 删除 Boot
        deleted_boot = mongo_delete_one("boots", filter_dict={"world_id": world_id})
        if deleted_boot:
            logger.info(f"删除 Boot 成功")

        # 删除 Dungeon
        deleted_dungeon = mongo_delete_one(
            "dungeons", filter_dict={"world_id": world_id}
        )
        if deleted_dungeon:
            logger.info(f"删除 Dungeon 成功")

        # 删除 WorldDocument
        success = mongo_delete_one("worlds", filter_dict={"_id": world_id})

        if success:
            logger.info(f"World 删除完成: ID={world_id}")
        else:
            logger.warning(f"World 删除失败: ID={world_id}")

        return success

    except Exception as e:
        logger.error(f"删除 World 失败: {e}")
        raise


###############################################################################################################################################
