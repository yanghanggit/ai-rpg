
from loguru import logger
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

import os
import traceback
from typing import Annotated, Dict, List, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import BaseMessage
from pydantic import SecretStr
from langchain.schema import HumanMessage, AIMessage
from langgraph.graph.state import CompiledStateGraph


############################################################################################################
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


############################################################################################################
class RAGState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_query: str  # 用户原始查询
    retrieved_docs: List[str]  # 模拟检索到的文档
    enhanced_context: str  # 增强后的上下文


############################################################################################################
# 模拟测试数据 - 基于艾尔法尼亚世界设定的专有知识库
MOCK_KNOWLEDGE_BASE = {
    "艾尔法尼亚": [
        "艾尔法尼亚大陆分为三大王国：人类的阿斯特拉王国、精灵的月桂森林联邦、兽人的铁爪部族联盟。",
        "大陆中央矗立着古老的封印之塔，传说圣剑「晨曦之刃」就封印在塔顶，用来镇压魔王的力量。",
        "艾尔法尼亚的魔法体系分为五个学派：火焰、冰霜、雷电、治愈和暗影，每个种族都有其擅长的魔法流派。",
    ],
    "圣剑": [
        "晨曦之刃是传说中的圣剑，剑身由星辰钢打造，剑柄镶嵌着光明神的眼泪结晶。",
        "只有拥有纯洁之心的勇者才能拔出圣剑，据说上一位持剑者是300年前的勇者莉莉丝。",
        "圣剑具有三种神圣技能：净化之光（驱散黑暗魔法）、审判之炎（对邪恶生物造成巨大伤害）、希望守护（保护队友免受致命伤害）。",
    ],
    "魔王": [
        "黑暗魔王阿巴顿曾经统治艾尔法尼亚大陆，将其变成死亡与绝望的土地。",
        "阿巴顿拥有不死之身，唯一能彻底消灭他的方法是用圣剑击中他的黑暗之心。",
        "最近黑暗气息再度出现，村民报告在月圆之夜听到魔王的咆哮声从封印之塔传来。",
    ],
    "种族": [
        "人类以阿斯特拉王国为中心，擅长锻造和贸易，他们的骑士团以重甲和长剑闻名。",
        "精灵居住在月桂森林，寿命可达千年，是最优秀的弓箭手和自然魔法师。",
        "兽人部族生活在北方山脉，身体强壮，崇尚武力，他们的战士可以徒手撕裂钢铁。",
        "还有传说中的龙族隐居在云端，偶尔会与勇敢的冒险者签订契约。",
    ],
    "遗迹": [
        "失落的贤者之塔：古代魔法师的研究所，内藏强大的魔法道具和禁忌知识。",
        "沉没的水晶城：曾经的矮人王国，因挖掘过深触怒了地底魔物而被淹没。",
        "暗影墓地：魔王军队的埋骨之地，据说夜晚会有亡灵士兵游荡。",
        "星辰神殿：供奉光明神的圣地，神殿中的圣水可以治愈任何诅咒。",
    ],
    "冒险者": [
        "艾尔法尼亚的冒险者公会总部位于阿斯特拉王国首都，分为青铜、白银、黄金、铂金四个等级。",
        "最著名的冒险者小队是「暴风雪团」，由人类剑士加伦、精灵法师艾莉娅和兽人战士格罗姆组成。",
        "冒险者的基本装备包括：附魔武器、魔法药水、探测魔物的水晶球和紧急传送卷轴。",
    ],
}


############################################################################################################
def retrieval_node(state: RAGState) -> Dict[str, Any]:
    """模拟文档检索节点"""
    try:
        logger.info("🔍 [RETRIEVAL] 开始检索相关文档...")

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

        # 简单的关键词匹配检索
        retrieved_docs = []
        query_lower = user_query.lower()

        for keyword, docs in MOCK_KNOWLEDGE_BASE.items():
            if keyword in query_lower:
                retrieved_docs.extend(docs)
                logger.info(
                    f"🔍 [RETRIEVAL] 匹配关键词 '{keyword}', 找到 {len(docs)} 个文档"
                )

        # 如果没有匹配到任何关键词，返回通用信息
        if not retrieved_docs:
            retrieved_docs = [
                "抱歉，没有找到相关的具体信息，我会尽力根据常识回答您的问题。"
            ]
            logger.warning("🔍 [RETRIEVAL] 未找到匹配文档，使用默认回复")

        logger.success(
            f"🔍 [RETRIEVAL] 检索完成，共找到 {len(retrieved_docs)} 个相关文档"
        )

        return {"user_query": user_query, "retrieved_docs": retrieved_docs}

    except Exception as e:
        logger.error(f"🔍 [RETRIEVAL] 检索节点错误: {e}\n{traceback.format_exc()}")
        return {
            "user_query": state.get("user_query", ""),
            "retrieved_docs": ["检索过程中发生错误，将使用默认回复。"],
        }


############################################################################################################
def context_enhancement_node(state: RAGState) -> Dict[str, Any]:
    """模拟上下文增强节点"""
    try:
        logger.info("📝 [ENHANCEMENT] 开始增强上下文...")

        user_query = state.get("user_query", "")
        retrieved_docs = state.get("retrieved_docs", [])

        logger.info(f"📝 [ENHANCEMENT] 处理查询: {user_query}")
        logger.info(f"📝 [ENHANCEMENT] 检索到的文档数量: {len(retrieved_docs)}")

        # 构建增强的上下文prompt
        context_parts = [
            "请基于以下相关信息回答用户的问题:",
            "",
            "相关信息:",
        ]

        for i, doc in enumerate(retrieved_docs, 1):
            context_parts.append(f"{i}. {doc}")

        context_parts.extend(
            ["", f"用户问题: {user_query}", "", "请基于上述信息给出准确、有帮助的回答:"]
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
    """RAG聊天系统主函数"""
    logger.info("🎯 启动RAG测试聊天系统...")

    # 聊天历史
    chat_history_state: State = {"messages": []}

    # 生成RAG状态图
    rag_compiled_graph = create_rag_compiled_graph()

    logger.success("🎯 RAG系统初始化完成，开始对话...")
    logger.info("💡 提示：您可以询问关于艾尔法尼亚世界的问题，例如：")
    logger.info("   - 艾尔法尼亚大陆有哪些王国？")
    logger.info("   - 圣剑有什么特殊能力？")
    logger.info("   - 魔王阿巴顿的弱点是什么？")
    logger.info("   - 有哪些种族生活在这片大陆？")
    logger.info("   - 著名的遗迹有哪些？")
    logger.info("   - 冒险者公会是如何运作的？")
    logger.info("💡 输入 /quit、/exit 或 /q 退出程序")

    while True:
        try:
            print("\n" + "=" * 60)
            user_input = input("User: ")

            if user_input.lower() in ["/quit", "/exit", "/q"]:
                print("Goodbye!")
                break

            # 用户输入
            user_input_state: State = {"messages": [HumanMessage(content=user_input)]}

            # 执行RAG流程
            update_messages = stream_rag_graph_updates(
                rag_compiled_graph=rag_compiled_graph,
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
                logger.success(f"✅ RAG回答: {latest_response.content}")

            logger.debug("=" * 60)

        except Exception as e:
            logger.error(
                f"❌ RAG流程处理错误: {e}\n" f"Traceback: {traceback.format_exc()}"
            )
            print("抱歉，处理您的请求时发生错误，请重试。")


############################################################################################################
if __name__ == "__main__":
    # 启动RAG聊天系统
    main()
