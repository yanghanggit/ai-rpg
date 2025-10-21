#!/usr/bin/env python3
"""
DeepSeek Chat Server启动脚本

功能：
1. 基于FastAPI构建的DeepSeek聊天服务器
2. 提供RESTful API接口
3. 支持聊天历史和上下文记忆
4. 异步处理聊天请求

使用方法：
    python scripts/run_deepseek_chat_server.py

或者在项目根目录下：
    python -m scripts.run_deepseek_chat_server

API端点：
    GET  /                    - 健康检查
    POST /api/chat/v1/        - 标准聊天
    POST /api/chat/rag/v1/    - RAG聊天
    POST /api/chat/undefined/v1/ - 未定义类型聊天
    POST /api/chat/mcp/v1/    - MCP聊天
"""

import os
from pathlib import Path
import sys
import asyncio
from typing import Any, Dict

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from fastapi import FastAPI
from loguru import logger

from ai_rpg.chat_services.protocol import ChatRequest, ChatResponse
from ai_rpg.deepseek import (
    State,
    create_compiled_stage_graph,
    stream_graph_updates,
    create_deepseek_llm,
    create_rag_compiled_graph,
    stream_rag_graph_updates,
    create_unified_chat_graph,
    stream_unified_graph_updates,
    McpState,
    create_compiled_mcp_stage_graph,
    stream_mcp_graph_updates,
)

from ai_rpg.configuration import (
    server_configuration,
)

# 导入路由管理器相关模块
from ai_rpg.rag.routing import (
    KeywordRouteStrategy,
    SemanticRouteStrategy,
    RouteDecisionManager,
    FallbackRouteStrategy,
    RouteConfigBuilder,
)
from ai_rpg.demo.campaign_setting import (
    FANTASY_WORLD_RPG_TEST_ROUTE_KEYWORDS,
    FANTASY_WORLD_RPG_TEST_RAG_TOPICS,
)

# 导入 MCP 相关模块
from ai_rpg.mcp import (
    McpToolInfo,
    initialize_mcp_client,
    McpConfig,
    load_mcp_config,
    McpClient,
)
from typing import List, Optional, Dict, Any
from langchain.schema import SystemMessage, BaseMessage
from ai_rpg.mcp.config import McpConfig
from contextlib import asynccontextmanager
from typing import AsyncGenerator

##################################################################################################################
# 全局 MCP 客户端和工具变量
_global_mcp_client: Optional[McpClient] = None
_global_available_tools: List[McpToolInfo] = []


##################################################################################################################
# MCP 相关配置和初始化函数
def _load_mcp_config_for_server() -> McpConfig:
    """为服务器加载 MCP 配置"""
    try:
        return load_mcp_config(Path("mcp_config.json"))
    except Exception as e:
        logger.error(f"加载 MCP 配置失败: {e}，使用默认配置")
        return McpConfig(
            mcp_server_host="127.0.0.1",
            mcp_server_port=8765,
            protocol_version="2024-11-05",
            mcp_timeout=30,
            server_name="Default MCP Server",
            server_version="1.0.0",
            server_description="默认 MCP 服务器配置",
            transport="streamable-http",
            allowed_origins=["http://localhost"],
        )


##################################################################################################################
async def _initialize_global_mcp_client() -> None:
    """全局初始化 MCP 客户端（服务器启动时调用一次）"""
    global _global_mcp_client, _global_available_tools

    try:
        logger.info("🔧 开始初始全局MCP客户端...")
        mcp_config = _load_mcp_config_for_server()
        mcp_client = await initialize_mcp_client(
            mcp_server_url=mcp_config.mcp_server_url,
            mcp_protocol_version=mcp_config.protocol_version,
            mcp_timeout=mcp_config.mcp_timeout,
        )

        if mcp_client:
            tools_result = await mcp_client.list_tools()
            available_tools = tools_result if tools_result is not None else []

            # 设置全局变量
            _global_mcp_client = mcp_client
            _global_available_tools = available_tools

            logger.success(
                f"🔗 全局MCP客户端初始化成功，可用工具: {len(available_tools)}"
            )
        else:
            logger.error("❌ 全局MCP客户端初始化失败")
            _global_mcp_client = None
            _global_available_tools = []

    except Exception as e:
        logger.error(f"❌ 全局MCP客户端初始化错误: {e}")
        _global_mcp_client = None
        _global_available_tools = []


##################################################################################################################
# 路由管理器创建函数
def _create_keyword_strategy() -> KeywordRouteStrategy:
    """创建艾尔法尼亚世界专用的关键词策略"""
    config = {
        "keywords": FANTASY_WORLD_RPG_TEST_ROUTE_KEYWORDS,
        "threshold": 0.1,  # 较低阈值，只要匹配到关键词就启用RAG
        "case_sensitive": False,
    }
    return KeywordRouteStrategy(config)


##################################################################################################################
def _create_game_semantic_strategy() -> SemanticRouteStrategy:
    """创建游戏专用的语义路由策略"""
    config = {
        "similarity_threshold": 0.5,  # 中等相似度阈值
        "use_multilingual": True,  # 使用多语言模型支持中文
        "rag_topics": FANTASY_WORLD_RPG_TEST_RAG_TOPICS,
    }
    return SemanticRouteStrategy(config)


##################################################################################################################
def _create_default_route_manager() -> RouteDecisionManager:
    """创建默认的路由决策管理器"""
    # 创建策略实例
    keyword_strategy = _create_keyword_strategy()
    semantic_strategy = _create_game_semantic_strategy()

    # 使用构建器创建管理器
    builder = RouteConfigBuilder()
    builder.add_strategy(keyword_strategy, 0.4)
    builder.add_strategy(semantic_strategy, 0.6)
    builder.set_fallback(FallbackRouteStrategy(default_to_rag=False))

    return builder.build()


##################################################################################################################


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理器（现代化方式）

    在应用启动时执行初始化逻辑，在关闭时执行清理逻辑
    """
    # 启动时执行
    logger.info("🚀 应用启动中...")
    await _initialize_global_mcp_client()
    logger.success("✅ 应用启动完成")

    yield  # 应用运行期间

    # 关闭时执行（如果需要清理资源）
    logger.info("🔄 应用关闭中...")
    # 这里可以添加清理逻辑，比如关闭数据库连接等
    logger.success("✅ 应用关闭完成")


# 初始化 FastAPI 应用（使用现代化生命周期管理）
app = FastAPI(
    title="DeepSeek Chat Server",
    description="基于DeepSeek的聊天服务器",
    version="1.0.0",
    lifespan=lifespan,
)


##################################################################################################################
# 健康检查端点
@app.get("/")
async def health_check() -> Dict[str, Any]:
    """
    服务器健康检查端点

    Returns:
        dict: 包含服务器状态信息的字典
    """
    from datetime import datetime

    return {
        "service": "DeepSeek Chat Server",
        "version": "1.0.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "available_endpoints": [
            "GET /",
            "POST /api/chat/v1/",
            "POST /api/chat/rag/v1/",
            "POST /api/chat/undefined/v1/",
            "POST /api/chat/mcp/v1/",
        ],
        "description": "基于DeepSeek的聊天服务器正在正常运行",
    }


##################################################################################################################
# 定义 POST 请求处理逻辑
@app.post(
    path="/api/chat/v1/",
    response_model=ChatResponse,
)
async def process_chat_request(payload: ChatRequest) -> ChatResponse:
    """
    处理聊天请求

    Args:
        request: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象
    """
    try:
        logger.info(f"收到聊天请求: {payload.message.content}")

        # 为每个请求创建独立的LLM实例
        llm = create_deepseek_llm()

        # 为每个请求创建独立的状态图实例
        compiled_state_graph = create_compiled_stage_graph("deepseek_chatbot_node")

        # 聊天历史（包含LLM实例）
        chat_history_state: State = {
            "messages": [message for message in payload.chat_history],
            "llm": llm,
        }

        # 用户输入
        user_input_state: State = {"messages": [payload.message], "llm": llm}

        # 获取回复 - 使用 asyncio.to_thread 将阻塞调用包装为异步
        update_messages = await asyncio.to_thread(
            stream_graph_updates,
            state_compiled_graph=compiled_state_graph,
            chat_history_state=chat_history_state,
            user_input_state=user_input_state,
        )

        logger.success(f"生成回复消息数量: {len(update_messages)}")

        # 打印所有消息的详细内容
        for i, message in enumerate(update_messages):
            logger.success(f"消息 {i+1}: {message.model_dump_json(indent=2)}")

        # 返回
        return ChatResponse(messages=update_messages)

    except Exception as e:
        logger.error(f"处理聊天请求时发生错误: {e}")
        # 返回错误消息
        from langchain.schema import AIMessage

        error_message = AIMessage(content=f"抱歉，处理您的请求时发生错误: {str(e)}")
        return ChatResponse(messages=[error_message])


##################################################################################################################
@app.post(
    path="/api/chat/rag/v1/",
    response_model=ChatResponse,
)
async def process_chat_rag_request(payload: ChatRequest) -> ChatResponse:
    """
    处理RAG聊天请求

    Args:
        request: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象
    """
    try:
        logger.info(f"收到RAG聊天请求: {payload.message.content}")

        # 为每个请求创建独立的LLM实例
        llm = create_deepseek_llm()

        # 为每个请求创建独立的RAG状态图实例
        rag_compiled_graph = create_rag_compiled_graph()

        # 聊天历史（包含LLM实例）
        chat_history_state: State = {
            "messages": [message for message in payload.chat_history],
            "llm": llm,
        }

        # 用户输入
        user_input_state: State = {"messages": [payload.message], "llm": llm}

        # 获取RAG回复 - 使用 asyncio.to_thread 将阻塞调用包装为异步
        update_messages = await asyncio.to_thread(
            stream_rag_graph_updates,
            rag_compiled_graph=rag_compiled_graph,
            chat_history_state=chat_history_state,
            user_input_state=user_input_state,
        )

        logger.success(f"生成RAG回复消息数量: {len(update_messages)}")

        # 打印所有消息的详细内容
        for i, message in enumerate(update_messages):
            logger.success(f"RAG消息 {i+1}: {message.model_dump_json(indent=2)}")

        # 返回
        return ChatResponse(messages=update_messages)

    except Exception as e:
        logger.error(f"处理RAG聊天请求时发生错误: {e}")
        # 返回错误消息
        from langchain.schema import AIMessage

        error_message = AIMessage(content=f"抱歉，处理您的RAG请求时发生错误: {str(e)}")
        return ChatResponse(messages=[error_message])


##################################################################################################################
@app.post(
    path="/api/chat/undefined/v1/",
    response_model=ChatResponse,
)
async def process_chat_undefined_request(payload: ChatRequest) -> ChatResponse:
    """
    处理统一聊天请求（智能路由）

    功能特性：
    1. 🚦 智能路由：自动检测查询类型并选择最佳处理模式
    2. 💬 直接对话：一般性聊天使用DeepSeek直接回答
    3. 🔍 RAG增强：艾尔法尼亚世界相关问题使用知识库增强
    4. 🎯 无缝切换：用户无需手动选择模式

    Args:
        request: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象
    """
    try:
        logger.info(f"收到统一聊天请求: {payload.message.content}")

        # 创建统一聊天图
        unified_graph = create_unified_chat_graph()

        # 创建路由管理器实例
        route_manager = _create_default_route_manager()

        # 聊天历史状态（使用字典格式，符合统一图的要求）
        chat_history_state: Dict[str, List[BaseMessage]] = {
            "messages": [message for message in payload.chat_history]
        }

        # 用户输入状态
        user_input_state: Dict[str, List[BaseMessage]] = {"messages": [payload.message]}

        # 执行统一聊天流程 - 使用 asyncio.to_thread 将阻塞调用包装为异步
        update_messages = await asyncio.to_thread(
            stream_unified_graph_updates,
            unified_compiled_graph=unified_graph,
            chat_history_state=chat_history_state,
            user_input_state=user_input_state,
            route_manager=route_manager,
        )

        logger.success(f"生成统一聊天回复消息数量: {len(update_messages)}")

        # 打印所有消息的详细内容
        for i, message in enumerate(update_messages):
            logger.success(f"统一聊天消息 {i+1}: {message.model_dump_json(indent=2)}")

        # 返回
        return ChatResponse(messages=update_messages)

    except Exception as e:
        logger.error(f"处理统一聊天请求时发生错误: {e}")
        # 返回错误消息
        from langchain.schema import AIMessage

        error_message = AIMessage(
            content=f"抱歉，处理您的统一聊天请求时发生错误: {str(e)}"
        )
        return ChatResponse(messages=[error_message])


##################################################################################################################
@app.post(
    path="/api/chat/mcp/v1/",
    response_model=ChatResponse,
)
async def process_chat_mcp_request(payload: ChatRequest) -> ChatResponse:
    """
    处理MCP聊天请求

    功能特性：
    1. 🔧 工具调用：支持 Model Context Protocol (MCP) 工具集成
    2. 🤖 智能助手：基于 DeepSeek AI 的强大对话能力
    3. 🔗 实时连接：动态连接和管理 MCP 服务器
    4. ⚡ 异步处理：高效的异步工具调用和响应

    Args:
        request: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象
    """
    try:
        logger.info(f"收到MCP聊天请求: {payload.message.content}")

        # 获取全局 MCP 客户端和工具
        global _global_mcp_client, _global_available_tools
        mcp_client, available_tools = _global_mcp_client, _global_available_tools

        if mcp_client is None:
            # MCP 服务器连接失败，返回错误信息
            from langchain.schema import AIMessage

            error_message = AIMessage(
                content="❌ MCP 服务器连接失败。请确保 MCP 服务器正在运行，启动命令：python scripts/run_sample_mcp_server.py --config mcp_config.json"
            )
            return ChatResponse(messages=[error_message])

        # 设置系统提示（可以根据需要调整）
        system_prompt = """你是一个智能AI助手，具备工具调用能力。你可以使用各种工具来帮助用户完成任务，包括获取时间、系统信息等。当用户询问相关信息时，你应该主动使用相应的工具来获取准确的信息。"""

        # 创建 MCP 聊天历史状态
        # 类型断言：此时 mcp_client 已经确保不为 None
        assert mcp_client is not None
        chat_history_state: McpState = {
            "messages": [SystemMessage(content=system_prompt)]
            + [message for message in payload.chat_history],
            "mcp_client": mcp_client,
            "available_tools": available_tools,
            "tool_outputs": [],
        }

        # 用户输入状态
        user_input_state: McpState = {
            "messages": [payload.message],
            "mcp_client": mcp_client,
            "available_tools": available_tools,
            "tool_outputs": [],
        }

        # 创建 MCP 状态图实例
        compiled_mcp_stage_graph = await create_compiled_mcp_stage_graph(
            "deepseek_mcp_chatbot_node",
            mcp_client,
        )

        # 获取 MCP 回复（包含可能的工具调用）- 使用异步包装
        update_messages = await stream_mcp_graph_updates(
            state_compiled_graph=compiled_mcp_stage_graph,
            chat_history_state=chat_history_state,
            user_input_state=user_input_state,
        )

        logger.success(f"生成MCP回复消息数量: {len(update_messages)}")

        # 打印所有消息的详细内容
        for i, message in enumerate(update_messages):
            logger.success(f"MCP消息 {i+1}: {message.model_dump_json(indent=2)}")

        # 返回
        return ChatResponse(messages=update_messages)

    except Exception as e:
        logger.error(f"处理MCP聊天请求时发生错误: {e}")
        # 返回错误消息
        from langchain.schema import AIMessage

        error_message = AIMessage(content=f"抱歉，处理您的MCP请求时发生错误: {str(e)}")
        return ChatResponse(messages=[error_message])


##################################################################################################################
def main() -> None:
    """
    DeepSeek聊天服务器主函数

    功能：
    1. 启动FastAPI服务器
    2. 配置服务器参数
    3. 提供聊天API服务
    """
    logger.info("🚀 启动DeepSeek聊天服务器...")

    # 加载服务器配置
    # server_config = initialize_server_settings_instance(
    #     Path("server_configuration.json")
    # )

    try:
        import uvicorn

        # 启动服务器
        uvicorn.run(
            app,
            host="localhost",
            port=server_configuration.deepseek_chat_server_port,
            log_level="debug",
        )

    except Exception as e:
        logger.error(f"❌ 启动服务器失败: {e}")
        raise


##################################################################################################################
if __name__ == "__main__":
    main()
