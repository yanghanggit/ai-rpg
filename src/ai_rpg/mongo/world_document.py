"""
World 相关的 MongoDB 文档模型和存储操作
"""

from datetime import datetime
from typing import final, List, Dict
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from loguru import logger
from ..models.world import World
from .agent_document import save_agent_contexts, load_agent_contexts
from .client import mongo_upsert_one, mongo_find_one


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

        # TODO: 后续添加
        # - 存储 entities_serialization
        # - 存储 dungeon
        # - 存储 boot

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

        # 创建不完整的 World 对象
        world = World(
            runtime_index=world_doc_dict.get("runtime_index", 1000),  # 加载运行时索引
            agents_context=agents_context,
            # 其他字段使用默认值（后续实现完整加载）
            # entities_serialization=[],
            # dungeon=Dungeon(name=""),
            # boot=Boot(name=""),
        )

        logger.info(f"World 加载完成: ID={world_id}")
        return world

    except Exception as e:
        logger.error(f"加载 World 失败: {e}")
        raise


###############################################################################################################################################
