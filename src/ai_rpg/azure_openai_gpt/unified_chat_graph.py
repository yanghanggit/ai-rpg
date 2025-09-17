from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import traceback
from typing import Annotated, Any, Dict, List, Literal, Optional

from langchain.schema import AIMessage, HumanMessage
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

# 导入ChromaDB相关功能
from ..chroma import get_chroma_db
from ..rag import rag_semantic_search

# 导入新的路由系统
from ..rag.routing import RouteDecisionManager

# 导入统一的 Azure OpenAI GPT 客户端
from .client import create_azure_openai_gpt_llm
from langchain_openai import AzureChatOpenAI


############################################################################################################
class UnifiedState(TypedDict):
    """统一状态定义，支持直接对话和RAG两种模式"""

    messages: Annotated[List[BaseMessage], add_messages]
    user_query: str  # 用户原始查询
    route_decision: str  # 路由决策结果："direct" | "rag"

    # RAG专用字段（可选）
    retrieved_docs: Optional[List[str]]  # 检索到的文档
    enhanced_context: Optional[str]  # 增强后的上下文
    similarity_scores: Optional[List[float]]  # 相似度分数

    # 路由元信息
    confidence_score: float  # 路由决策的置信度
    processing_mode: str  # 处理模式描述

    # 路由管理器（必传）
    route_manager: Optional[RouteDecisionManager]  # 路由决策管理器实例（通过参数传入）

    # LLM实例（统一管理）
    llm: AzureChatOpenAI  # Azure OpenAI GPT实例，在图级别共享


############################################################################################################
def router_node(state: UnifiedState) -> Dict[str, Any]:
    """
    路由决策节点 - 重构版本

    使用可配置的路由策略进行决策，支持关键词匹配、语义分析等多种策略组合。
    """
    try:
        logger.info("🚦 [ROUTER] 开始路由决策...")

        user_query = state.get("user_query", "")
        if not user_query:
            # 从最新消息中提取查询
            if state.get("messages"):
                last_message = state["messages"][-1]
                if isinstance(last_message, HumanMessage):
                    content = last_message.content
                    user_query = content if isinstance(content, str) else str(content)

        logger.info(f"🚦 [ROUTER] 分析用户查询: {user_query}")

        # 直接从状态中获取路由管理器
        route_manager = state["route_manager"]
        if route_manager is None:
            raise RuntimeError("路由管理器不能为空，请检查参数传递")

        decision = route_manager.make_decision(user_query)

        # 转换决策结果到原有格式
        route_decision = "rag" if decision.should_use_rag else "direct"
        confidence_score = decision.confidence

        # 构建处理模式描述
        if decision.should_use_rag:
            # 从元数据中提取策略信息
            if decision.metadata:
                strategies_used = decision.metadata.get("strategies_used", [])
                processing_mode = f"RAG增强模式 (策略: {', '.join(strategies_used)})"
            else:
                processing_mode = "RAG增强模式"
        else:
            processing_mode = "直接对话模式"

        logger.success(
            f"🚦 [ROUTER] 路由决策完成: {route_decision} (置信度: {confidence_score:.2f})"
        )

        # 记录详细的决策信息
        try:
            if decision.metadata:
                individual_decisions = decision.metadata.get("individual_decisions", {})
                for strategy_name, strategy_info in individual_decisions.items():
                    logger.debug(
                        f"🚦 [ROUTER] {strategy_name}: "
                        f"RAG={strategy_info['should_use_rag']}, "
                        f"置信度={strategy_info['confidence']:.3f}, "
                        f"权重={strategy_info['weight']}"
                    )
        except Exception:
            # 忽略日志记录错误
            pass

        return {
            "user_query": user_query,
            "route_decision": route_decision,
            "confidence_score": confidence_score,
            "processing_mode": processing_mode,
            # 保留决策详情用于调试和分析
            "route_metadata": decision.metadata,
        }

    except Exception as e:
        logger.error(f"🚦 [ROUTER] 路由决策错误: {e}\n{traceback.format_exc()}")
        # 默认回退到直接对话模式
        return {
            "user_query": state.get("user_query", ""),
            "route_decision": "direct",
            "confidence_score": 0.1,
            "processing_mode": "错误回退-直接对话模式",
            "route_metadata": {"error": str(e)},
        }


############################################################################################################
def direct_llm_node(state: UnifiedState) -> Dict[str, List[BaseMessage]]:
    """
    直接LLM对话节点

    功能：
    - 直接使用Azure OpenAI GPT进行对话，无额外上下文增强
    - 适用于一般性对话和简单问答
    """
    try:
        logger.info("💬 [DIRECT_LLM] 开始直接对话模式...")

        # 使用状态中的LLM实例
        llm = state["llm"]
        assert llm is not None, "LLM instance is None in state"

        # 直接使用原始消息调用LLM
        response = llm.invoke(state["messages"])
        logger.success("💬 [DIRECT_LLM] 直接对话回答生成完成")

        return {"messages": [response]}

    except Exception as e:
        logger.error(f"💬 [DIRECT_LLM] 直接对话节点错误: {e}\n{traceback.format_exc()}")
        error_response = AIMessage(content="抱歉，生成回答时发生错误，请稍后重试。")
        return {"messages": [error_response]}


############################################################################################################
def retrieval_node(state: UnifiedState) -> Dict[str, Any]:
    """
    RAG检索节点

    功能：
    - ChromaDB向量语义搜索
    - 获取相关文档和相似度分数
    - 为后续上下文增强提供数据
    """
    try:
        logger.info("🔍 [RETRIEVAL] 开始RAG检索...")

        user_query = state.get("user_query", "")
        logger.info(f"🔍 [RETRIEVAL] 用户查询: {user_query}")

        # 获取ChromaDB实例并执行语义搜索
        chroma_db = get_chroma_db()

        if not chroma_db.initialized:
            logger.error("❌ [RETRIEVAL] ChromaDB未初始化，无法执行搜索")
            return {
                "retrieved_docs": ["ChromaDB数据库未初始化，请检查系统配置。"],
                "similarity_scores": [0.0],
            }

        # 执行向量语义搜索
        retrieved_docs, similarity_scores = rag_semantic_search(
            query=user_query, top_k=5
        )

        # 检查搜索结果
        if not retrieved_docs:
            logger.warning("🔍 [RETRIEVAL] 语义搜索未找到相关文档，使用默认回复")
            retrieved_docs = [
                "抱歉，没有找到相关的具体信息，我会尽力根据常识回答您的问题。"
            ]
            similarity_scores = [0.0]

        # 过滤低相似度结果（相似度阈值：0.3）
        MIN_SIMILARITY = 0.3
        filtered_docs = []
        filtered_scores = []

        for doc, score in zip(retrieved_docs, similarity_scores):
            if score >= MIN_SIMILARITY:
                filtered_docs.append(doc)
                filtered_scores.append(score)

        # 如果过滤后没有文档，保留最高分的文档
        if not filtered_docs and retrieved_docs:
            filtered_docs = [retrieved_docs[0]]
            filtered_scores = [similarity_scores[0]]
            logger.info(
                f"🔍 [RETRIEVAL] 所有结果低于阈值，保留最高分文档 (相似度: {similarity_scores[0]:.3f})"
            )

        logger.success(
            f"🔍 [RETRIEVAL] 语义检索完成，共找到 {len(filtered_docs)} 个相关文档"
        )

        # 记录相似度信息
        for i, (doc, score) in enumerate(zip(filtered_docs, filtered_scores)):
            logger.debug(f"  📄 [{i+1}] 相似度: {score:.3f}, 内容: {doc[:50]}...")

        return {
            "retrieved_docs": filtered_docs,
            "similarity_scores": filtered_scores,
        }

    except Exception as e:
        logger.error(f"🔍 [RETRIEVAL] 检索节点错误: {e}\n{traceback.format_exc()}")
        return {
            "retrieved_docs": ["检索过程中发生错误，将使用默认回复。"],
            "similarity_scores": [0.0],
        }


############################################################################################################
def enhancement_node(state: UnifiedState) -> Dict[str, Any]:
    """
    上下文增强节点

    功能：
    - 构建包含检索结果的增强提示
    - 添加相似度信息和处理指导
    - 为RAG LLM节点提供优化的上下文
    """
    try:
        logger.info("📝 [ENHANCEMENT] 开始上下文增强...")

        user_query = state.get("user_query", "")
        retrieved_docs = state.get("retrieved_docs", [])
        similarity_scores = state.get("similarity_scores", [])

        logger.info(f"📝 [ENHANCEMENT] 处理查询: {user_query}")
        logger.info(
            f"📝 [ENHANCEMENT] 检索到的文档数量: {len(retrieved_docs) if retrieved_docs else 0}"
        )

        if similarity_scores:
            avg_similarity = sum(similarity_scores) / len(similarity_scores)
            max_similarity = max(similarity_scores)
            logger.info(
                f"📝 [ENHANCEMENT] 平均相似度: {avg_similarity:.3f}, 最高相似度: {max_similarity:.3f}"
            )

        # 构建增强的上下文prompt
        context_parts = [
            "请基于以下相关信息回复用户:",
            "",
            "相关信息 (按相似度排序):",
        ]

        # 将文档和相似度分数配对，并按相似度排序
        if (
            similarity_scores
            and retrieved_docs
            and len(similarity_scores) == len(retrieved_docs)
        ):
            doc_score_pairs = list(zip(retrieved_docs, similarity_scores))
            # 按相似度降序排序
            doc_score_pairs.sort(key=lambda x: x[1], reverse=True)

            for i, (doc, score) in enumerate(doc_score_pairs, 1):
                # 添加相似度信息到上下文中
                context_parts.append(f"{i}. [相似度: {score:.3f}] {doc}")
        else:
            # 回退到原来的格式（没有相似度信息）
            if retrieved_docs:
                for i, doc in enumerate(retrieved_docs, 1):
                    context_parts.append(f"{i}. {doc}")

        context_parts.extend(
            [
                "",
                f"用户问题: {user_query}",
                "",
                "请基于上述信息给出准确、有帮助的回答:",
                "- 优先使用相似度较高的信息",
                "- 如果相似度较低，请适当提醒用户",
                "- 保持回答的准确性和相关性",
                "- 如果信息不足，请诚实说明并提供可能的帮助",
            ]
        )

        enhanced_context = "\n".join(context_parts)

        logger.info("📝 [ENHANCEMENT] 上下文增强完成")
        logger.debug(
            f"📝 [ENHANCEMENT] 增强后的上下文长度: {len(enhanced_context)} 字符"
        )

        return {"enhanced_context": enhanced_context}

    except Exception as e:
        logger.error(
            f"📝 [ENHANCEMENT] 上下文增强节点错误: {e}\n{traceback.format_exc()}"
        )
        fallback_context = f"请回答以下问题: {state.get('user_query', '')}"
        return {"enhanced_context": fallback_context}


############################################################################################################
def rag_llm_node(state: UnifiedState) -> Dict[str, List[BaseMessage]]:
    """
    RAG增强LLM节点

    功能：
    - 使用增强的上下文调用Azure OpenAI GPT
    - 生成基于检索信息的专业回答
    """
    try:
        logger.info("🤖 [RAG_LLM] 开始RAG增强回答生成...")

        # 使用状态中的LLM实例
        llm = state["llm"]
        assert llm is not None, "LLM instance is None in state"

        # 使用增强的上下文替换原始消息
        enhanced_context = state.get("enhanced_context", "")
        if enhanced_context:
            enhanced_message = HumanMessage(content=enhanced_context)
            logger.info("🤖 [RAG_LLM] 使用增强上下文调用Azure OpenAI GPT")
        else:
            # 回退到原始消息
            if state["messages"]:
                last_msg = state["messages"][-1]
                if isinstance(last_msg, HumanMessage):
                    enhanced_message = last_msg
                else:
                    content = (
                        last_msg.content
                        if isinstance(last_msg.content, str)
                        else str(last_msg.content)
                    )
                    enhanced_message = HumanMessage(content=content)
            else:
                enhanced_message = HumanMessage(content="Hello")
            logger.warning("🤖 [RAG_LLM] 增强上下文为空，使用原始消息")

        # 调用LLM
        response = llm.invoke([enhanced_message])
        logger.success("🤖 [RAG_LLM] RAG增强回答生成完成")

        return {"messages": [response]}

    except Exception as e:
        logger.error(f"🤖 [RAG_LLM] RAG LLM节点错误: {e}\n{traceback.format_exc()}")
        error_response = AIMessage(content="抱歉，生成回答时发生错误，请稍后重试。")
        return {"messages": [error_response]}


############################################################################################################
def route_decision_function(state: UnifiedState) -> Literal["direct", "rag"]:
    """
    路由决策函数

    用于LangGraph的条件边，根据状态中的route_decision字段返回路由目标
    """
    route = state.get("route_decision", "direct")
    logger.info(f"🚦 [ROUTE_DECISION] 执行路由: {route}")
    return route  # type: ignore


############################################################################################################
def create_unified_chat_graph() -> (
    CompiledStateGraph[UnifiedState, Any, UnifiedState, UnifiedState]
):
    """
    创建统一的聊天图

    图结构：
    router → [条件分支] → direct_llm | (retrieval → enhancement → rag_llm)
    """
    logger.info("🏗️ 构建统一聊天图...")

    try:
        # 创建状态图
        graph_builder = StateGraph(UnifiedState)

        # 添加所有节点
        graph_builder.add_node("router", router_node)
        graph_builder.add_node("direct_llm", direct_llm_node)
        graph_builder.add_node("retrieval", retrieval_node)
        graph_builder.add_node("enhancement", enhancement_node)
        graph_builder.add_node("rag_llm", rag_llm_node)

        # 设置入口点
        graph_builder.set_entry_point("router")

        # 添加条件路由
        graph_builder.add_conditional_edges(
            "router",
            route_decision_function,
            {"direct": "direct_llm", "rag": "retrieval"},
        )

        # RAG分支内部连接
        graph_builder.add_edge("retrieval", "enhancement")
        graph_builder.add_edge("enhancement", "rag_llm")

        # 设置终点
        graph_builder.set_finish_point("direct_llm")
        graph_builder.set_finish_point("rag_llm")

        compiled_graph = graph_builder.compile()
        logger.success("🏗️ 统一聊天图构建完成")

        return compiled_graph  # type: ignore[return-value]

    except Exception as e:
        logger.error(f"🏗️ 构建统一聊天图失败: {e}\n{traceback.format_exc()}")
        raise


############################################################################################################
def stream_unified_graph_updates(
    unified_compiled_graph: CompiledStateGraph[
        UnifiedState, Any, UnifiedState, UnifiedState
    ],
    chat_history_state: Dict[str, List[BaseMessage]],
    user_input_state: Dict[str, List[BaseMessage]],
    route_manager: RouteDecisionManager,
) -> List[BaseMessage]:
    """
    执行统一图并返回结果

    Args:
        unified_compiled_graph: 编译后的统一图
        chat_history_state: 聊天历史状态
        user_input_state: 用户输入状态
        route_manager: 路由决策管理器实例（必传）

    Returns:
        List[BaseMessage]: 生成的回答消息列表
    """
    ret: List[BaseMessage] = []

    try:
        logger.info("🚀 开始执行统一聊天流程...")

        # 创建 Azure OpenAI GPT 实例
        llm = create_azure_openai_gpt_llm()
        logger.info("🚀 创建 Azure OpenAI GPT 实例完成")

        # 准备统一状态
        user_message = (
            user_input_state["messages"][-1] if user_input_state["messages"] else None
        )
        user_query = ""
        if user_message:
            content = user_message.content
            user_query = content if isinstance(content, str) else str(content)

        unified_state: UnifiedState = {
            "messages": chat_history_state["messages"] + user_input_state["messages"],
            "user_query": user_query,
            "route_decision": "",  # 将由router_node填充
            "retrieved_docs": None,
            "enhanced_context": None,
            "similarity_scores": None,
            "confidence_score": 0.0,
            "processing_mode": "",
            "route_manager": route_manager,  # 直接使用传入的route_manager
            "llm": llm,  # 添加LLM实例到状态中
        }

        logger.info(f"🚀 统一状态准备完成，用户查询: {user_query}")

        # 执行统一图流程
        for event in unified_compiled_graph.stream(unified_state):
            logger.debug(f"🚀 统一图事件: {list(event.keys())}")
            for node_name, node_output in event.items():
                if "messages" in node_output:
                    ret.extend(node_output["messages"])
                    logger.info(
                        f"🚀 节点 [{node_name}] 输出消息数量: {len(node_output['messages'])}"
                    )

        logger.success("🚀 统一聊天流程执行完成")

    except Exception as e:
        logger.error(f"🚀 统一聊天流程执行错误: {e}\n{traceback.format_exc()}")
        error_response = AIMessage(content="统一聊天流程执行时发生错误，请稍后重试。")
        ret = [error_response]

    return ret
