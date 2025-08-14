from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
import traceback
from typing import Annotated, Any, Dict, List, Literal, Optional

from langchain.schema import AIMessage, HumanMessage
from langchain_core.messages import BaseMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr
from typing_extensions import TypedDict

# 导入ChromaDB相关功能
from ..db.chromadb_client import get_chroma_db
from ..db.rag_ops import rag_semantic_search


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


############################################################################################################
def router_node(state: UnifiedState) -> Dict[str, Any]:
    """
    路由决策节点

    基于关键词的简单路由策略：
    - 检测艾尔法尼亚世界相关关键词
    - 决定使用直接对话还是RAG增强模式
    """
    try:
        logger.info("🚦 [ROUTER] 开始路由决策...")

        user_query = state.get("user_query", "")
        if not user_query:
            # 从最新消息中提取查询
            if state["messages"]:
                last_message = state["messages"][-1]
                if isinstance(last_message, HumanMessage):
                    content = last_message.content
                    user_query = content if isinstance(content, str) else str(content)

        logger.info(f"🚦 [ROUTER] 分析用户查询: {user_query}")

        # 艾尔法尼亚世界相关关键词
        rag_keywords = [
            # 地名和世界设定
            "艾尔法尼亚",
            "阿斯特拉王国",
            "月桂森林联邦",
            "铁爪部族联盟",
            "封印之塔",
            "贤者之塔",
            "水晶城",
            "暗影墓地",
            "星辰神殿",
            # 重要物品和角色
            "圣剑",
            "晨曦之刃",
            "魔王",
            "玛拉凯斯",
            "黯蚀之主",
            "勇者",
            "莉莉丝",
            # 种族和职业
            "精灵",
            "兽人",
            "龙族",
            "矮人",
            "冒险者",
            "骑士",
            "法师",
            "战士",
            # 魔法和技能
            "火焰",
            "冰霜",
            "雷电",
            "治愈",
            "暗影",
            "净化之光",
            "审判之炎",
            "希望守护",
            # 组织和物品
            "冒险者公会",
            "暴风雪团",
            "时之沙漏",
            "生命之泉",
            "星辰钢",
            "魔法药水",
            # 通用游戏术语
            "王国",
            "联邦",
            "部族",
            "遗迹",
            "地下城",
            "魔法",
            "技能",
            "装备",
            "等级",
        ]

        # 检查关键词匹配
        query_lower = user_query.lower()
        matched_keywords = [
            keyword for keyword in rag_keywords if keyword in query_lower
        ]

        # 路由决策逻辑
        if matched_keywords:
            route_decision = "rag"
            confidence_score = min(0.9, 0.5 + len(matched_keywords) * 0.1)
            processing_mode = f"RAG增强模式 (匹配关键词: {', '.join(matched_keywords[:3])}{'...' if len(matched_keywords) > 3 else ''})"
            logger.success(
                f"🚦 [ROUTER] 选择RAG模式，匹配到 {len(matched_keywords)} 个关键词"
            )
        else:
            route_decision = "direct"
            confidence_score = 0.8
            processing_mode = "直接对话模式"
            logger.info("🚦 [ROUTER] 选择直接对话模式，未检测到专业关键词")

        logger.info(
            f"🚦 [ROUTER] 路由决策完成: {route_decision} (置信度: {confidence_score:.2f})"
        )

        return {
            "user_query": user_query,
            "route_decision": route_decision,
            "confidence_score": confidence_score,
            "processing_mode": processing_mode,
        }

    except Exception as e:
        logger.error(f"🚦 [ROUTER] 路由决策错误: {e}\n{traceback.format_exc()}")
        # 默认回退到直接对话模式
        return {
            "user_query": state.get("user_query", ""),
            "route_decision": "direct",
            "confidence_score": 0.5,
            "processing_mode": "错误回退-直接对话模式",
        }


############################################################################################################
def direct_llm_node(state: UnifiedState) -> Dict[str, List[BaseMessage]]:
    """
    直接LLM对话节点

    功能：
    - 直接使用DeepSeek进行对话，无额外上下文增强
    - 适用于一般性对话和简单问答
    """
    try:
        logger.info("💬 [DIRECT_LLM] 开始直接对话模式...")

        # 检查必需的环境变量
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        if not deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

        llm = ChatDeepSeek(
            api_key=SecretStr(deepseek_api_key),
            model="deepseek-chat",
            temperature=0.7,
        )

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
            "请基于以下相关信息回答用户的问题:",
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
    - 使用增强的上下文调用DeepSeek
    - 生成基于检索信息的专业回答
    """
    try:
        logger.info("🤖 [RAG_LLM] 开始RAG增强回答生成...")

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
            logger.info("🤖 [RAG_LLM] 使用增强上下文调用DeepSeek")
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
) -> List[BaseMessage]:
    """
    执行统一图并返回结果

    Args:
        unified_compiled_graph: 编译后的统一图
        chat_history_state: 聊天历史状态
        user_input_state: 用户输入状态

    Returns:
        List[BaseMessage]: 生成的回答消息列表
    """
    ret: List[BaseMessage] = []

    try:
        logger.info("🚀 开始执行统一聊天流程...")

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


############################################################################################################
def main() -> None:
    """
    统一聊天系统主函数

    功能：
    - 创建统一聊天图
    - 提供交互式命令行界面
    - 支持直接对话和RAG增强两种模式的智能切换
    """
    logger.info("🎯 启动统一聊天系统...")

    try:
        # 创建统一聊天图
        unified_graph = create_unified_chat_graph()

        # 初始化聊天历史
        chat_history_state: Dict[str, List[BaseMessage]] = {"messages": []}

        logger.success("🎯 统一聊天系统初始化完成")
        logger.info("💡 提示：系统会自动检测您的查询类型并选择最佳处理模式")
        logger.info("   - 涉及艾尔法尼亚世界的问题将使用RAG增强模式")
        logger.info("   - 一般性对话将使用直接对话模式")
        logger.info("💡 输入 /quit、/exit 或 /q 退出程序")

        # 开始交互循环
        while True:
            try:
                print("\n" + "=" * 60)
                user_input = input("User: ")

                if user_input.lower() in ["/quit", "/exit", "/q"]:
                    print("Goodbye!")
                    break

                # 用户输入状态
                user_input_state: Dict[str, List[BaseMessage]] = {
                    "messages": [HumanMessage(content=user_input)]
                }

                # 执行统一图流程
                update_messages = stream_unified_graph_updates(
                    unified_compiled_graph=unified_graph,
                    chat_history_state=chat_history_state,
                    user_input_state=user_input_state,
                )

                # 更新聊天历史
                chat_history_state["messages"].extend(user_input_state["messages"])
                chat_history_state["messages"].extend(update_messages)

                # 显示最新的AI回复
                if update_messages:
                    latest_response = update_messages[-1]
                    print(f"\nDeepSeek: {latest_response.content}")
                    logger.success(f"✅ 系统回答: {latest_response.content}")

                logger.debug("=" * 60)

            except KeyboardInterrupt:
                logger.info("🛑 [MAIN] 用户中断程序")
                break
            except Exception as e:
                logger.error(f"❌ 统一聊天流程处理错误: {e}\n{traceback.format_exc()}")
                print("抱歉，处理您的请求时发生错误，请重试。")

    except Exception as e:
        logger.error(f"❌ [MAIN] 统一聊天系统启动失败: {e}")
        print("系统启动失败，请检查环境配置。")

    finally:
        logger.info("🔒 [MAIN] 清理系统资源...")


############################################################################################################
if __name__ == "__main__":
    main()
