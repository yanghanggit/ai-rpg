"""
AgentContext 和 AgentMessage 的 MongoDB 文档模型

设计思路：
1. agent_contexts: 存储对话元数据（轻量级，支持快速查询）
2. agent_messages: 存储完整消息内容（使用 model_dump_json 序列化）

优势：
- 突破 16MB 单文档限制
- 支持按需加载消息内容
- 保证 LangChain Message 对象的完整性
"""

from datetime import datetime
from typing import List, Literal, final, Dict
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from loguru import logger
from ..models.world import AgentContext
from .client import mongo_upsert_one, mongo_find_many


###############################################################################################################################################
@final
class AgentMessageMetadata(BaseModel):
    """
    消息元数据 - 存储在 AgentContext 中的轻量级引用
    """

    message_id: str = Field(..., description="消息ID，关联到 agent_messages 集合")
    type: Literal["system", "human", "ai"] = Field(..., description="消息类型")
    index: int = Field(..., description="消息序号，保证顺序")
    timestamp: datetime = Field(default_factory=datetime.now, description="消息时间戳")


###############################################################################################################################################
@final
class AgentContextDocument(BaseModel):
    """
    MongoDB 文档模型：Agent 对话上下文元数据

    存储 Agent 的对话历史元数据，不包含消息的完整内容。
    实际消息内容存储在 agent_messages 集合中。
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="_id",
        description="AgentContext 唯一标识符",
    )
    world_id: str = Field(..., description="关联的 World 文档 ID")
    agent_name: str = Field(..., description="Agent 名称")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="最后更新时间"
    )
    message_count: int = Field(default=0, description="消息总数")
    messages: List[AgentMessageMetadata] = Field(
        default_factory=list, description="消息元数据列表"
    )


###############################################################################################################################################
@final
class AgentMessageDocument(BaseModel):
    """
    MongoDB 文档模型：Agent 消息完整内容

    存储单条消息的完整内容，使用 model_dump_json() 序列化 LangChain Message 对象。
    通过 message_id 与 AgentContext 关联。
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="_id",
        description="消息唯一标识符",
    )
    agent_context_id: str = Field(..., description="关联的 AgentContext 文档 ID")
    world_id: str = Field(..., description="关联的 World 文档 ID")
    agent_name: str = Field(..., description="Agent 名称")
    type: Literal["system", "human", "ai"] = Field(..., description="消息类型")
    index: int = Field(..., description="消息序号")
    timestamp: datetime = Field(default_factory=datetime.now, description="消息时间戳")
    message_data: str = Field(
        ...,
        description="消息完整内容的 JSON 字符串（由 message.model_dump_json() 生成）",
    )


###############################################################################################################################################
def save_agent_contexts(
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
def load_agent_contexts(world_id: str) -> Dict[str, AgentContext]:
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
