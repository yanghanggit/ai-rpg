"""
World 相关的 MongoDB 文档模型和存储操作
"""

from datetime import datetime
from typing import final, List, Dict
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from loguru import logger
from ..models.world import World, AgentContext
from .agent_document import (
    AgentContextDocument,
    AgentMessageMetadata,
)
from .client import mongo_upsert_one, mongo_find_one, mongo_find_many


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
def _save_world_agent_contexts(
    agents_context: Dict[str, AgentContext], world_id: str
) -> List[str]:
    """
    存储所有 AgentContext 到 MongoDB

    参数:
        agents_context: Agent 名称到 AgentContext 的映射
        world_id: World 文档的 ID，用于关联 AgentContext

    返回:
        List[str]: 成功存储的 AgentContext 文档 ID 列表

    说明:
        - 将每个 AgentContext 存储为独立文档
        - 每个 AgentContext 的消息列表会被转换为元数据引用
        - 实际消息内容会在后续步骤存储到 agent_messages 集合
    """
    saved_ids: List[str] = []

    try:
        for agent_name, agent_context in agents_context.items():
            # 创建 AgentContext 文档
            context_doc = AgentContextDocument(
                world_id=world_id,
                agent_name=agent_name,
                message_count=len(agent_context.context),
                messages=[
                    AgentMessageMetadata(
                        message_id=f"msg_{world_id}_{agent_name}_{idx}",
                        type=msg.type,  # 获取消息类型
                        index=idx,
                    )
                    for idx, msg in enumerate(agent_context.context)
                ],
            )

            # 存储到 MongoDB
            # 注意：这里使用复合条件 (world_id + agent_name) 确保唯一性
            # 但 mongo_upsert_one 只支持单个 filter_key，所以使用 _id
            doc_dict = context_doc.model_dump(by_alias=True)
            result_id = mongo_upsert_one(
                "agent_contexts",
                doc_dict,
                filter_key="_id",  # 使用 _id 作为唯一标识
            )

            if result_id:
                saved_ids.append(result_id)
                logger.debug(
                    f"存储 AgentContext 成功: {agent_name}, "
                    f"消息数: {len(agent_context.context)}, ID: {result_id}"
                )
            else:
                logger.warning(f"存储 AgentContext 失败: {agent_name}")

        logger.info(
            f"批量存储 AgentContext 完成，成功: {len(saved_ids)}/{len(agents_context)}"
        )
        return saved_ids

    except Exception as e:
        logger.error(f"存储 AgentContexts 失败: {e}")
        raise


###############################################################################################################################################
def _load_world_agent_contexts(world_id: str) -> Dict[str, AgentContext]:
    """
    从 MongoDB 加载所有 AgentContext

    参数:
        world_id: World 文档的 ID

    返回:
        Dict[str, AgentContext]: Agent 名称到 AgentContext 的映射

    说明:
        - 从 agent_contexts 集合加载所有关联到该 world_id 的文档
        - 目前只加载元数据，不加载实际消息内容（message_data）
        - 返回的 AgentContext 的 context 列表为空（后续实现消息加载）
    """
    try:
        # 查询所有属于该 world_id 的 AgentContext 文档
        context_docs = mongo_find_many(
            "agent_contexts", filter_dict={"world_id": world_id}
        )

        agents_context: Dict[str, AgentContext] = {}

        for doc in context_docs:
            agent_name = doc["agent_name"]
            # 创建 AgentContext（暂时不加载消息内容）
            agent_context = AgentContext(
                name=agent_name,
                context=[],  # TODO: 后续从 agent_messages 加载实际消息
            )
            agents_context[agent_name] = agent_context

            logger.debug(
                f"加载 AgentContext: {agent_name}, "
                f"消息数(元数据): {doc.get('message_count', 0)}"
            )

        logger.info(f"加载 {len(agents_context)} 个 AgentContext")
        return agents_context

    except Exception as e:
        logger.error(f"加载 AgentContexts 失败: {e}")
        raise


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
        saved_context_ids = _save_world_agent_contexts(world.agents_context, world_id)
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
        agents_context = _load_world_agent_contexts(world_id)

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
