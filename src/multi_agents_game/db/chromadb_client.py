import traceback
from typing import List, Optional, Dict

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from loguru import logger

from ..utils.model_loader import load_multilingual_model
from ..config import DEFAULT_RAG_CONFIG

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

    def __init__(self, collection_name: str, collection_description: str):
        """
        初始化ChromaDB向量数据库

        Args:
            collection_name: ChromaDB集合名称
            collection_description: 集合描述信息
        """
        self.collection_name = collection_name
        self.collection_description = collection_description
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

            # 1. 初始化ChromaDB持久化客户端
            persist_directory = "./chroma_db"
            self.client = chromadb.PersistentClient(path=persist_directory)
            logger.success(
                f"✅ [CHROMADB] ChromaDB持久化客户端创建成功，数据目录: {persist_directory}"
            )

            # 2. 加载SentenceTransformer模型（使用项目缓存）
            logger.info("🔄 [CHROMADB] 加载多语言语义模型...")
            self.embedding_model = load_multilingual_model()

            if self.embedding_model is None:
                logger.error("❌ [CHROMADB] 多语言模型加载失败")
                return False

            logger.success("✅ [CHROMADB] 多语言语义模型加载成功")

            # 3. 检查集合是否已存在（持久化场景）
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
                existing_count = self.collection.count()
                logger.info(
                    f"� [CHROMADB] 发现已存在的集合: {self.collection_name}，包含 {existing_count} 个文档"
                )

                # 如果集合已有数据，跳过重新加载
                if existing_count > 0:
                    logger.info("✅ [CHROMADB] 使用现有持久化数据，跳过重新加载")
                    self.initialized = True
                    logger.success("🎉 [CHROMADB] 向量数据库初始化完成！")
                    return True

            except Exception:
                # 集合不存在，创建新集合
                logger.info(
                    f"🔄 [CHROMADB] 集合不存在，创建新集合: {self.collection_name}"
                )

            # 4. 创建新的ChromaDB集合（如果不存在或为空）
            if not self.collection:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": self.collection_description},
                )
                logger.success(f"✅ [CHROMADB] 集合创建成功: {self.collection_name}")

            self.initialized = True
            logger.success("🎉 [CHROMADB] 向量数据库初始化完成！")
            return True

        except Exception as e:
            logger.error(f"❌ [CHROMADB] 初始化失败: {e}\n{traceback.format_exc()}")
            return False

    def load_knowledge_base(self, knowledge_base: Dict[str, List[str]]) -> bool:
        """
        将知识库数据加载到ChromaDB中

        Args:
            knowledge_base: 知识库数据，格式为 {category: [documents]}

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
            for category, docs in knowledge_base.items():
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
        """关闭数据库连接（清理资源），数据已持久化到磁盘"""
        try:
            if self.client and self.collection_name:
                # ChromaDB持久化客户端，数据已保存到磁盘
                logger.info("🔄 [CHROMADB] 数据库连接已清理，数据已持久化")
        except Exception as e:
            logger.warning(f"⚠️ [CHROMADB] 关闭数据库时出现警告: {e}")


############################################################################################################
def get_chroma_db(
    collection_name: Optional[str] = None, collection_description: Optional[str] = None
) -> ChromaRAGDatabase:
    """
    获取全局ChromaDB实例（单例模式）

    Args:
        collection_name: 集合名称，如果不提供则使用默认配置
        collection_description: 集合描述，如果不提供则使用默认配置

    Returns:
        ChromaRAGDatabase: 全局数据库实例
    """
    global _chroma_db
    if _chroma_db is None:
        _chroma_db = ChromaRAGDatabase(
            collection_name or DEFAULT_RAG_CONFIG["collection_name"],
            collection_description or DEFAULT_RAG_CONFIG["description"],
        )
    return _chroma_db


############################################################################################################
def chromadb_clear_database() -> None:
    """
    完全清空ChromaDB持久化数据库
    注意：该方法会删除所有持久化数据，包括磁盘文件，请谨慎使用
    """
    import shutil
    import os

    try:
        global _chroma_db

        # 如果有现有实例，先关闭
        if _chroma_db:
            _chroma_db.close()
            _chroma_db = None

        # 删除持久化数据目录
        persist_directory = "./chroma_db"
        if os.path.exists(persist_directory):
            shutil.rmtree(persist_directory)
            logger.warning(f"🗑️ [CHROMADB] 已删除持久化数据目录: {persist_directory}")
        else:
            logger.info(f"📁 [CHROMADB] 持久化数据目录不存在: {persist_directory}")

        logger.warning("🔄 [CHROMADB] ChromaDB持久化数据库已被完全清除")

    except Exception as e:
        logger.error(f"❌ 清空ChromaDB持久化数据库时发生错误: {e}")
        logger.info("💡 建议手动删除 ./chroma_db 目录")
        raise


############################################################################################################
def chromadb_reset_database(knowledge_base: Dict[str, List[str]]) -> None:
    """
    清空ChromaDB数据库并重建（保留持久化能力）
    注意：该方法会删除所有数据，然后重新加载指定数据

    Args:
        collection_name: 集合名称
        collection_description: 集合描述
        knowledge_base: 要加载的知识库数据
    """
    try:
        global _chroma_db

        # 先清空数据库
        chromadb_clear_database()

        # 重新创建并初始化
        chroma_db = get_chroma_db()
        success = chroma_db.initialize()

        if success:
            # 加载知识库数据
            load_success = chroma_db.load_knowledge_base(knowledge_base)
            if load_success:
                logger.warning("🔄 ChromaDB持久化数据库已被清除然后重建")
            else:
                raise RuntimeError("ChromaDB知识库数据加载失败")
        else:
            raise RuntimeError("ChromaDB数据库重建失败")

    except Exception as e:
        logger.error(f"❌ 重置ChromaDB数据库时发生错误: {e}")
        logger.info("💡 建议检查ChromaDB配置和依赖")
        raise


############################################################################################################
def initialize_rag_system(knowledge_base: Dict[str, List[str]]) -> bool:
    """
    初始化RAG系统

    功能：
    1. 初始化ChromaDB向量数据库
    2. 加载SentenceTransformer模型
    3. 将知识库数据向量化并存储
    4. 验证系统就绪状态

    Args:
        collection_name: 集合名称
        collection_description: 集合描述
        knowledge_base: 要加载的知识库数据

    Returns:
        bool: 初始化是否成功
    """
    logger.info("🚀 [INIT] 开始初始化RAG系统...")

    try:
        # 获取ChromaDB实例并初始化
        chroma_db = get_chroma_db()
        success = chroma_db.initialize()

        if success:
            # 检查是否需要加载知识库数据
            if chroma_db.collection and chroma_db.collection.count() == 0:
                logger.info("📚 [INIT] 集合为空，开始加载知识库数据...")
                load_success = chroma_db.load_knowledge_base(knowledge_base)
                if not load_success:
                    logger.error("❌ [INIT] 知识库数据加载失败")
                    return False

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
