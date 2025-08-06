import traceback
from typing import List, Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from loguru import logger

from ..utils.model_loader import load_multilingual_model

############################################################################################################
# 全局ChromaDB实例
_chroma_db: Optional["ChromaRAGDatabase"] = None


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
                self.client.delete_collection(name=self.collection_name)
                logger.info(f"🗑️ [CHROMADB] 已删除旧集合: {self.collection_name}")
            except Exception:
                pass  # 集合不存在，忽略错误

            # 4. 创建新的ChromaDB集合
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "艾尔法尼亚世界知识库向量数据库"},
            )
            logger.success(f"✅ [CHROMADB] 集合创建成功: {self.collection_name}")

            # 5. 加载知识库数据
            success = self._load_knowledge_base()
            if not success:
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
                    metadatas.append({"category": category, "doc_id": doc_id})
                    ids.append(f"{category}_{doc_id}")
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
                logger.error("❌ [CHROMADB] 数据库未初始化")
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
                similarity_scores = [
                    max(0, 1 - (dist / max_distance)) for dist in distances
                ]
            else:
                similarity_scores = []

            logger.info(f"✅ [CHROMADB] 搜索完成，找到 {len(documents)} 个相关文档")

            # 打印搜索结果详情（用于调试）
            for i, (doc, score, metadata) in enumerate(
                zip(documents, similarity_scores, metadatas)
            ):
                logger.debug(
                    f"  📄 [{i+1}] 相似度: {score:.3f}, 类别: {metadata.get('category', 'unknown')}, 内容: {doc[:50]}..."
                )

            return documents, similarity_scores

        except Exception as e:
            logger.error(f"❌ [CHROMADB] 语义搜索失败: {e}\n{traceback.format_exc()}")
            return [], []

    def close(self) -> None:
        """关闭数据库连接（清理资源）"""
        try:
            if self.client and self.collection_name:
                # ChromaDB是无状态的，无需显式关闭
                logger.info("🔄 [CHROMADB] 数据库连接已清理")
        except Exception as e:
            logger.warning(f"⚠️ [CHROMADB] 关闭数据库时出现警告: {e}")


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
def chromadb_ensure_database_ready() -> None:
    """
    确保ChromaDB数据库已初始化并准备就绪
    这个函数在需要时才会被调用，避免导入时立即连接数据库
    """
    try:
        chroma_db = get_chroma_db()
        if not chroma_db.initialized:
            success = chroma_db.initialize()
            if not success:
                raise RuntimeError("ChromaDB数据库初始化失败")
        logger.info("✅ ChromaDB数据库已确保就绪")
    except Exception as e:
        logger.error(f"❌ 确保ChromaDB数据库就绪时出错: {e}")
        raise


############################################################################################################
def chromadb_reset_database() -> None:
    """
    清空ChromaDB数据库并重建
    注意：该方法会删除所有数据，只适用于开发环境
    """
    try:
        global _chroma_db

        # 如果有现有实例，先关闭
        if _chroma_db:
            _chroma_db.close()
            _chroma_db = None

        # 重新创建并初始化
        chroma_db = get_chroma_db()
        success = chroma_db.initialize()

        if success:
            logger.warning("🔄 ChromaDB数据库已被清除然后重建")
        else:
            raise RuntimeError("ChromaDB数据库重建失败")

    except Exception as e:
        logger.error(f"❌ 重置ChromaDB数据库时发生错误: {e}")
        logger.info("💡 建议检查ChromaDB配置和依赖")
        raise


############################################################################################################
def chromadb_semantic_search(
    query: str, top_k: int = 5
) -> tuple[List[str], List[float]]:
    """
    执行语义搜索的便捷函数

    Args:
        query: 用户查询文本
        top_k: 返回最相似的文档数量

    Returns:
        tuple: (检索到的文档列表, 相似度分数列表)
    """
    try:
        chroma_db = get_chroma_db()
        if not chroma_db.initialized:
            chromadb_ensure_database_ready()

        return chroma_db.semantic_search(query, top_k)

    except Exception as e:
        logger.error(f"❌ ChromaDB语义搜索失败: {e}")
        return [], []


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
            logger.success("🎉 [INIT] RAG系统初始化完成！")
            return True
        else:
            logger.error("❌ [INIT] RAG系统初始化失败")
            return False

    except Exception as e:
        logger.error(f"❌ [INIT] 初始化过程中发生错误: {e}\n{traceback.format_exc()}")
        logger.warning("⚠️ [INIT] 系统将回退到关键词匹配模式")
        return False


############################################################################################################
