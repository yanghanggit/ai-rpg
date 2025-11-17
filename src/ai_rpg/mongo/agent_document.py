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
from typing import List, Literal, final
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


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
