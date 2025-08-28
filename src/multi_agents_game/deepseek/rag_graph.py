from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
import traceback
from typing import Annotated, Any, Dict, List

from langchain.schema import AIMessage, HumanMessage
from langchain_core.messages import BaseMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr
from typing_extensions import TypedDict

# 导入ChromaDB相关功能
from ..chroma import get_chroma_db


############################################################################################################
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


############################################################################################################
class RAGState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_query: str  # 用户原始查询
    retrieved_docs: List[str]  # 检索到的文档
    enhanced_context: str  # 增强后的上下文
    similarity_scores: List[float]  # 相似度分数（用于调试和分析）


############################################################################################################
############################################################################################################
############################################################################################################
def retrieval_node(state: RAGState) -> Dict[str, Any]:
    """
    ChromaDB向量检索节点

    功能改造：
    1. 将原来的关键词匹配改为ChromaDB语义向量搜索
    2. 使用SentenceTransformer计算查询向量
    3. 返回最相似的文档和相似度分数
    4. 保持原有的错误处理和日志记录
    """
    try:
        logger.info("🔍 [RETRIEVAL] 开始向量语义检索...")

        user_query = state.get("user_query", "")
        if not user_query:
            # 从最新消息中提取查询
            if state["messages"]:
                last_message = state["messages"][-1]
                if isinstance(last_message, HumanMessage):
                    # 确保content是字符串类型
                    content = last_message.content
                    user_query = content if isinstance(content, str) else str(content)

        logger.info(f"🔍 [RETRIEVAL] 用户查询: {user_query}")

        # 获取ChromaDB实例并执行语义搜索
        chroma_db = get_chroma_db()

        if not chroma_db.initialized:
            logger.error("❌ [RETRIEVAL] ChromaDB未初始化，无法执行搜索")
            return {
                "user_query": user_query,
                "retrieved_docs": ["ChromaDB数据库未初始化，请检查系统配置。"],
                "similarity_scores": [0.0],
            }

        # 执行向量语义搜索
        from ..rag import rag_semantic_search

        retrieved_docs, similarity_scores = rag_semantic_search(
            query=user_query, top_k=5  # 返回最相似的5个文档
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
            logger.info(f"  📄 [{i+1}] 相似度: {score:.3f}, 内容: {doc[:50]}...")

        return {
            "user_query": user_query,
            "retrieved_docs": filtered_docs,
            "similarity_scores": filtered_scores,
        }

    except Exception as e:
        logger.error(f"🔍 [RETRIEVAL] 检索节点错误: {e}\n{traceback.format_exc()}")
        return {
            "user_query": state.get("user_query", ""),
            "retrieved_docs": ["检索过程中发生错误，将使用默认回复。"],
            "similarity_scores": [0.0],
        }


############################################################################################################
def context_enhancement_node(state: RAGState) -> Dict[str, Any]:
    """
    上下文增强节点（支持相似度信息）

    功能增强：
    1. 保持原有的上下文构建逻辑
    2. 添加相似度分数信息到上下文中
    3. 提供更丰富的检索质量信息
    4. 为LLM提供更好的参考依据
    """
    try:
        logger.info("📝 [ENHANCEMENT] 开始增强上下文...")

        user_query = state.get("user_query", "")
        retrieved_docs = state.get("retrieved_docs", [])
        similarity_scores = state.get("similarity_scores", [])

        logger.info(f"📝 [ENHANCEMENT] 处理查询: {user_query}")
        logger.info(f"📝 [ENHANCEMENT] 检索到的文档数量: {len(retrieved_docs)}")

        if similarity_scores:
            avg_similarity = sum(similarity_scores) / len(similarity_scores)
            max_similarity = max(similarity_scores)
            logger.info(
                f"📝 [ENHANCEMENT] 平均相似度: {avg_similarity:.3f}, 最高相似度: {max_similarity:.3f}"
            )

        # 构建增强的上下文prompt
        context_parts = [
            "请基于以下相关信息回答用户的问题:",
            "",
            "相关信息 (按相似度排序):",
        ]

        # 将文档和相似度分数配对，并按相似度排序
        if similarity_scores and len(similarity_scores) == len(retrieved_docs):
            doc_score_pairs = list(zip(retrieved_docs, similarity_scores))
            # 按相似度降序排序
            doc_score_pairs.sort(key=lambda x: x[1], reverse=True)

            for i, (doc, score) in enumerate(doc_score_pairs, 1):
                # 添加相似度信息到上下文中（帮助LLM理解检索质量）
                context_parts.append(f"{i}. [相似度: {score:.3f}] {doc}")
        else:
            # 回退到原来的格式（没有相似度信息）
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
            ]
        )

        enhanced_context = "\n".join(context_parts)

        logger.info("📝 [ENHANCEMENT] 上下文增强完成")
        logger.debug(f"📝 [ENHANCEMENT] 增强后的上下文:\n{enhanced_context}")

        return {"enhanced_context": enhanced_context}

    except Exception as e:
        logger.error(
            f"📝 [ENHANCEMENT] 上下文增强节点错误: {e}\n{traceback.format_exc()}"
        )
        fallback_context = f"请回答以下问题: {state.get('user_query', '')}"
        return {"enhanced_context": fallback_context}


############################################################################################################
def rag_llm_node(state: RAGState) -> Dict[str, List[BaseMessage]]:
    """RAG版本的LLM节点"""
    try:
        logger.info("🤖 [LLM] 开始生成回答...")

        # 检查必需的环境变量
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        if not deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

        llm = ChatDeepSeek(
            api_key=SecretStr(deepseek_api_key),
            model="deepseek-chat",
            temperature=0.7,
        )

        # 使用增强的上下文替换原始消息
        enhanced_context = state.get("enhanced_context", "")
        if enhanced_context:
            enhanced_message = HumanMessage(content=enhanced_context)
            logger.info("🤖 [LLM] 使用增强上下文调用DeepSeek")
        else:
            # 回退到原始消息，确保转换为HumanMessage
            if state["messages"]:
                last_msg = state["messages"][-1]
                if isinstance(last_msg, HumanMessage):
                    enhanced_message = last_msg
                else:
                    # 将其他类型的消息转换为HumanMessage
                    content = (
                        last_msg.content
                        if isinstance(last_msg.content, str)
                        else str(last_msg.content)
                    )
                    enhanced_message = HumanMessage(content=content)
            else:
                enhanced_message = HumanMessage(content="Hello")
            logger.warning("🤖 [LLM] 增强上下文为空，使用原始消息")

        # 调用LLM
        response = llm.invoke([enhanced_message])
        logger.success("🤖 [LLM] DeepSeek回答生成完成")

        return {"messages": [response]}

    except Exception as e:
        logger.error(f"🤖 [LLM] LLM节点错误: {e}\n{traceback.format_exc()}")
        error_response = AIMessage(content="抱歉，生成回答时发生错误，请稍后重试。")
        return {"messages": [error_response]}


############################################################################################################
def create_rag_compiled_graph() -> (
    CompiledStateGraph[RAGState, Any, RAGState, RAGState]
):
    """创建RAG测试版本的状态图"""
    logger.info("🏗️ 构建RAG状态图...")

    try:
        # 创建状态图
        graph_builder = StateGraph(RAGState)

        # 添加三个节点
        graph_builder.add_node("retrieval", retrieval_node)
        graph_builder.add_node("enhancement", context_enhancement_node)
        graph_builder.add_node("llm", rag_llm_node)

        # 设置节点流程: retrieval → enhancement → llm
        graph_builder.add_edge("retrieval", "enhancement")
        graph_builder.add_edge("enhancement", "llm")

        # 设置入口和出口点
        graph_builder.set_entry_point("retrieval")
        graph_builder.set_finish_point("llm")

        compiled_graph = graph_builder.compile()
        logger.success("🏗️ RAG状态图构建完成")

        # 明确类型转换以满足mypy要求
        return compiled_graph  # type: ignore[return-value]

    except Exception as e:
        logger.error(f"🏗️ 构建RAG状态图失败: {e}\n{traceback.format_exc()}")
        raise


############################################################################################################
def stream_rag_graph_updates(
    rag_compiled_graph: CompiledStateGraph[RAGState, Any, RAGState, RAGState],
    chat_history_state: State,
    user_input_state: State,
) -> List[BaseMessage]:
    """执行RAG状态图并返回结果"""

    ret: List[BaseMessage] = []

    try:
        logger.info("🚀 开始执行RAG流程...")

        # 准备RAG状态
        user_message = (
            user_input_state["messages"][-1] if user_input_state["messages"] else None
        )
        user_query = ""
        if user_message:
            content = user_message.content
            user_query = content if isinstance(content, str) else str(content)

        rag_state: RAGState = {
            "messages": chat_history_state["messages"] + user_input_state["messages"],
            "user_query": user_query,
            "retrieved_docs": [],
            "enhanced_context": "",
            "similarity_scores": [],  # 添加相似度分数字段
        }

        logger.info(f"🚀 RAG输入状态准备完成，用户查询: {user_query}")

        # 执行RAG流程
        for event in rag_compiled_graph.stream(rag_state):
            logger.debug(f"🚀 RAG流程事件: {list(event.keys())}")
            for node_name, node_output in event.items():
                if "messages" in node_output:
                    ret.extend(node_output["messages"])
                    logger.info(
                        f"🚀 节点 [{node_name}] 输出消息数量: {len(node_output['messages'])}"
                    )

        logger.success("🚀 RAG流程执行完成")

    except Exception as e:
        logger.error(f"🚀 RAG流程执行错误: {e}\n{traceback.format_exc()}")
        error_response = AIMessage(content="RAG流程执行时发生错误，请稍后重试。")
        ret = [error_response]

    return ret


############################################################################################################
def main() -> None:
    pass


############################################################################################################
if __name__ == "__main__":
    # 提示用户使用专用启动脚本
    main()
