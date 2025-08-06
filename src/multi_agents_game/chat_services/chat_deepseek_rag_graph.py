from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
import traceback
from typing import Annotated, Any, Dict, List, Optional

from langchain.schema import AIMessage, HumanMessage
from langchain_core.messages import BaseMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr
from typing_extensions import TypedDict
import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.api import ClientAPI
from ..utils.model_loader import load_multilingual_model


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
class ChromaRAGDatabase:
    """
    ChromaDB向量数据库管理类

    负责：
    1. 初始化ChromaDB客户端和集合
    2. 将知识库数据向量化并存储
    3. 提供语义搜索接口
    4. 管理向量数据库的生命周期
    """

    def __init__(self, collection_name: str = "alfania_knowledge_base"):
        """
        初始化ChromaDB向量数据库

        Args:
            collection_name: ChromaDB集合名称
        """
        self.collection_name = collection_name
        self.client: Optional[ClientAPI] = None
        self.collection: Optional[Collection] = None
        self.embedding_model = None
        self.initialized = False

        logger.info(f"🏗️ [CHROMADB] 初始化ChromaDB管理器，集合名称: {collection_name}")

    def initialize(self) -> bool:
        """
        初始化ChromaDB客户端、加载模型并创建集合

        Returns:
            bool: 初始化是否成功
        """
        try:
            logger.info("🚀 [CHROMADB] 开始初始化向量数据库...")

            # 1. 初始化ChromaDB客户端
            self.client = chromadb.Client()
            logger.success("✅ [CHROMADB] ChromaDB客户端创建成功")

            # 2. 加载SentenceTransformer模型（使用项目缓存）
            logger.info("🔄 [CHROMADB] 加载多语言语义模型...")
            self.embedding_model = load_multilingual_model()

            if self.embedding_model is None:
                logger.error("❌ [CHROMADB] 多语言模型加载失败")
                return False

            logger.success("✅ [CHROMADB] 多语言语义模型加载成功")

            # 3. 删除可能存在的旧集合（重新初始化）
            try:
                self.client.delete_collection(self.collection_name)
                logger.info(f"🗑️ [CHROMADB] 已删除旧集合: {self.collection_name}")
            except Exception:
                # 集合不存在，忽略错误
                pass

            # 4. 创建新的ChromaDB集合
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "艾尔法尼亚世界知识库向量数据库"},
            )
            logger.success(f"✅ [CHROMADB] 集合创建成功: {self.collection_name}")

            # 5. 加载知识库数据
            success = self._load_knowledge_base()
            if not success:
                logger.error("❌ [CHROMADB] 知识库数据加载失败")
                return False

            self.initialized = True
            logger.success("🎉 [CHROMADB] 向量数据库初始化完成！")
            return True

        except Exception as e:
            logger.error(f"❌ [CHROMADB] 初始化失败: {e}\n{traceback.format_exc()}")
            return False

    def _load_knowledge_base(self) -> bool:
        """
        将模拟知识库数据加载到ChromaDB中

        Returns:
            bool: 加载是否成功
        """
        try:
            logger.info("📚 [CHROMADB] 开始加载知识库数据...")

            if not self.collection or not self.embedding_model:
                logger.error("❌ [CHROMADB] 集合或模型未初始化")
                return False

            # 准备文档数据
            documents = []
            metadatas = []
            ids = []

            doc_id = 0
            for category, docs in MOCK_KNOWLEDGE_BASE.items():
                for doc in docs:
                    documents.append(doc)
                    metadatas.append(
                        {"category": category, "source": "艾尔法尼亚世界设定"}
                    )
                    ids.append(f"doc_{doc_id:03d}")
                    doc_id += 1

            logger.info(f"📊 [CHROMADB] 准备向量化 {len(documents)} 个文档...")

            # 使用SentenceTransformer计算向量嵌入
            logger.info("🔄 [CHROMADB] 计算文档向量嵌入...")
            embeddings = self.embedding_model.encode(documents)

            # 转换为列表格式（ChromaDB要求）
            embeddings_list = embeddings.tolist()

            # 批量添加到ChromaDB
            logger.info("💾 [CHROMADB] 存储向量到数据库...")
            self.collection.add(
                embeddings=embeddings_list,
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

            logger.success(
                f"✅ [CHROMADB] 成功加载 {len(documents)} 个文档到向量数据库"
            )

            # 验证数据加载
            count = self.collection.count()
            logger.info(f"📊 [CHROMADB] 数据库中现有文档数量: {count}")

            return True

        except Exception as e:
            logger.error(f"❌ [CHROMADB] 知识库加载失败: {e}\n{traceback.format_exc()}")
            return False

    def semantic_search(
        self, query: str, top_k: int = 5
    ) -> tuple[List[str], List[float]]:
        """
        执行语义搜索

        Args:
            query: 用户查询文本
            top_k: 返回最相似的文档数量

        Returns:
            tuple: (检索到的文档列表, 相似度分数列表)
        """
        try:
            if not self.initialized or not self.collection or not self.embedding_model:
                logger.error("❌ [CHROMADB] 数据库未初始化，无法执行搜索")
                return [], []

            logger.info(f"🔍 [CHROMADB] 执行语义搜索: '{query}'")

            # 计算查询向量
            query_embedding = self.embedding_model.encode([query])

            # 在ChromaDB中执行向量搜索
            results = self.collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=top_k,
                include=["documents", "distances", "metadatas"],
            )

            # 提取结果
            documents = results["documents"][0] if results["documents"] else []
            distances = results["distances"][0] if results["distances"] else []
            metadatas = results["metadatas"][0] if results["metadatas"] else []

            # 将距离转换为相似度分数（距离越小，相似度越高）
            # 相似度 = 1 - 标准化距离
            if distances:
                max_distance = max(distances) if distances else 1.0
                min_distance = min(distances) if distances else 0.0

                # 避免除零错误
                distance_range = max_distance - min_distance
                if distance_range == 0:
                    similarity_scores = [1.0] * len(distances)
                else:
                    similarity_scores = [
                        1.0 - (dist - min_distance) / distance_range
                        for dist in distances
                    ]
            else:
                similarity_scores = []

            logger.info(f"✅ [CHROMADB] 搜索完成，找到 {len(documents)} 个相关文档")

            # 打印搜索结果详情（用于调试）
            for i, (doc, score, metadata) in enumerate(
                zip(documents, similarity_scores, metadatas)
            ):
                category = metadata.get("category", "未知") if metadata else "未知"
                logger.debug(f"  📄 [{i+1}] 相似度: {score:.3f}, 类别: {category}")
                logger.debug(f"      内容: {doc[:100]}...")

            return documents, similarity_scores

        except Exception as e:
            logger.error(f"❌ [CHROMADB] 语义搜索失败: {e}\n{traceback.format_exc()}")
            return [], []

    def close(self) -> None:
        """关闭数据库连接（清理资源）"""
        try:
            if self.client and self.collection_name:
                # ChromaDB内存模式无需特殊清理
                logger.info("🔒 [CHROMADB] 数据库连接已关闭")
                self.initialized = False
        except Exception as e:
            logger.warning(f"⚠️ [CHROMADB] 关闭数据库时出现警告: {e}")


# 全局ChromaDB实例
_chroma_db: Optional[ChromaRAGDatabase] = None


def get_chroma_db() -> ChromaRAGDatabase:
    """
    获取全局ChromaDB实例（单例模式）

    Returns:
        ChromaRAGDatabase: 全局数据库实例
    """
    global _chroma_db
    if _chroma_db is None:
        _chroma_db = ChromaRAGDatabase()
    return _chroma_db


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
            logger.warning("⚠️ [RETRIEVAL] ChromaDB未初始化，回退到关键词匹配")
            # 回退到原来的关键词匹配逻辑
            return _fallback_keyword_search(user_query)

        # 执行向量语义搜索
        retrieved_docs, similarity_scores = chroma_db.semantic_search(
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


def _fallback_keyword_search(user_query: str) -> Dict[str, Any]:
    """
    回退函数：当ChromaDB不可用时使用原来的关键词匹配

    Args:
        user_query: 用户查询

    Returns:
        Dict: 包含检索结果的字典
    """
    logger.info("🔄 [RETRIEVAL] 使用关键词匹配回退逻辑...")

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

    return {
        "user_query": user_query,
        "retrieved_docs": retrieved_docs,
        "similarity_scores": [1.0] * len(retrieved_docs),  # 关键词匹配给满分
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
def initialize_rag_system() -> bool:
    """
    初始化RAG系统

    功能：
    1. 初始化ChromaDB向量数据库
    2. 加载SentenceTransformer模型
    3. 将知识库数据向量化并存储
    4. 验证系统就绪状态

    Returns:
        bool: 初始化是否成功
    """
    logger.info("🚀 [INIT] 开始初始化RAG系统...")

    try:
        # 获取ChromaDB实例并初始化
        chroma_db = get_chroma_db()
        success = chroma_db.initialize()

        if success:
            logger.success("✅ [INIT] RAG系统初始化完成！")
            logger.info("💡 [INIT] 系统现在支持:")
            logger.info("   🔍 语义向量搜索")
            logger.info("   📊 相似度评分")
            logger.info("   🎯 智能文档排序")
            logger.info("   💾 ChromaDB向量存储")
            return True
        else:
            logger.error("❌ [INIT] RAG系统初始化失败")
            logger.warning("⚠️ [INIT] 系统将回退到关键词匹配模式")
            return False

    except Exception as e:
        logger.error(f"❌ [INIT] 初始化过程中发生错误: {e}\n{traceback.format_exc()}")
        logger.warning("⚠️ [INIT] 系统将回退到关键词匹配模式")
        return False


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
    # """
    # 简化的main函数，主要用于库导入测试

    # 注意：实际的启动脚本已移至 scripts/run_chromadb_rag_chat.py
    # 建议使用: python scripts/run_chromadb_rag_chat.py
    # """
    # print("🎯 ChromaDB RAG 库已就绪")
    # print("💡 要启动交互式聊天系统，请运行:")
    # print("   python scripts/run_chromadb_rag_chat.py")
    # print("")
    # print("🔧 或者在代码中导入使用:")
    # print("   from src.multi_agents_game.chat_services.chat_deepseek_rag_graph import (")
    # print("       initialize_rag_system, create_rag_compiled_graph")
    # print("   )")


############################################################################################################
if __name__ == "__main__":
    # 提示用户使用专用启动脚本
    main()
