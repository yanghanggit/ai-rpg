"""DeepSeek 聊天服务模块

提供基于 DeepSeek 的聊天接口，支持标准聊天和推理模型。

本模块定义了所有 DeepSeek 聊天相关的 API 端点（业务逻辑层）：
- 标准聊天模型（deepseek-chat）：通用对话、工具调用、结构化输出
- 推理模型（deepseek-reasoner）：复杂推理、思维链、深度分析

架构说明：
- 使用 FastAPI APIRouter 实现路由注册
- 与主应用解耦，便于独立测试和复用
- 统一使用 chat_service.protocol 定义的请求/响应格式
- 通过 execute_chat_workflow 执行异步聊天流程

使用方式：
    from ai_rpg.services.deepseek_chat import deepseek_chat_api_router
    app.include_router(deepseek_chat_api_router)
"""

from fastapi import APIRouter
from loguru import logger
from ..chat_client.protocol import ChatRequest, ChatResponse
from ..deepseek import (
    create_chat_workflow,
    execute_chat_workflow,
    create_deepseek_chat,
    create_deepseek_reasoner,
)

###################################################################################################################################################################
# 创建 API Router
deepseek_chat_api_router = APIRouter()


###################################################################################################################################################################
@deepseek_chat_api_router.post("/api/chat/v1/", response_model=ChatResponse)
async def process_chat_request(payload: ChatRequest) -> ChatResponse:
    """
    处理标准聊天请求

    使用 deepseek-chat 模型处理聊天请求，支持：
    - 多轮对话上下文
    - 工具调用（Function Calling）
    - 结构化输出
    - 流式响应

    Args:
        payload: 包含聊天上下文和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象
    """
    try:
        logger.info(f"收到聊天请求: {payload.message.content}")

        chat_response = await execute_chat_workflow(
            work_flow=create_chat_workflow(),
            context=[message for message in payload.context],
            request=payload.message,
            llm=create_deepseek_chat(),
        )

        logger.success(f"生成回复消息数量: {len(chat_response)}")

        # 打印所有消息的详细内容
        for i, message in enumerate(chat_response):
            logger.success(f"消息 {i+1}: {message.model_dump_json(indent=2)}")

        # 返回
        return ChatResponse(messages=chat_response)

    except Exception as e:
        logger.error(f"处理聊天请求时发生错误: {e}")

    return ChatResponse(messages=[])


###################################################################################################################################################################
@deepseek_chat_api_router.post("/api/chat/reasoner/v1/", response_model=ChatResponse)
async def process_chat_reasoner_request(payload: ChatRequest) -> ChatResponse:
    """
    处理聊天请求（使用推理模型）

    特性：
    - 使用 DeepSeek Reasoner 模型（思考模式）
    - 提供推理思考过程（reasoning_content）
    - 适合复杂推理任务
    - 注意：不支持工具调用和结构化输出

    Args:
        payload: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象（包含思考过程）
    """
    try:
        logger.info(f"🧠 收到推理模型聊天请求: {payload.message.content}")

        chat_response = await execute_chat_workflow(
            work_flow=create_chat_workflow(),
            context=[message for message in payload.context],
            request=payload.message,
            llm=create_deepseek_reasoner(),  # 使用推理模型
        )

        logger.success(f"生成回复消息数量: {len(chat_response)}")

        # 打印所有消息的详细内容
        for i, message in enumerate(chat_response):
            logger.success(f"消息 {i+1}: {message.model_dump_json(indent=2)}")

        # 返回
        return ChatResponse(messages=chat_response)

    except Exception as e:
        logger.error(f"处理推理模型聊天请求时发生错误: {e}")
        return ChatResponse(messages=[])
