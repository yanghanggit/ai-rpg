import traceback
from pathlib import Path
from typing import List, Optional, Dict

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from loguru import logger

from ..config import DEFAULT_RAG_CONFIG
from .embedding_manager import (
    get_embedding_model,
    prepare_knowledge_base_for_embedding,
)

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
        self.initialized = False

        logger.info(f"🏗️ [CHROMADB] 初始化ChromaDB管理器，集合名称: {collection_name}")

    def _load_existing_collection(self) -> bool:
        """
        尝试加载已存在的ChromaDB集合

        Returns:
            bool: 是否成功加载已存在的集合（有数据）
        """
        try:
            if self.client is None:
                logger.error("❌ [CHROMADB] 客户端未初始化")
                return False

            self.collection = self.client.get_collection(name=self.collection_name)
            existing_count = self.collection.count()
            logger.info(
                f"📁 [CHROMADB] 发现已存在的集合: {self.collection_name}，包含 {existing_count} 个文档"
            )

            # 如果集合已有数据，可以直接使用
            if existing_count > 0:
                logger.info("✅ [CHROMADB] 使用现有持久化数据，跳过重新加载")
                return True
            else:
                logger.info("📋 [CHROMADB] 已存在的集合为空，需要重新加载数据")
                return False

        except Exception as e:
            # 集合不存在或访问失败
            logger.info(f"🔄 [CHROMADB] 集合不存在或访问失败: {e}")
            return False

    def _create_new_collection(self) -> bool:
        """
        创建新的ChromaDB集合

        Returns:
            bool: 是否成功创建新集合
        """
        try:
            if self.client is None:
                logger.error("❌ [CHROMADB] 客户端未初始化")
                return False

            # 如果集合已存在但为空，或者完全不存在，创建/重新创建集合
            if self.collection is None:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": self.collection_description},
                )
                logger.success(f"✅ [CHROMADB] 新集合创建成功: {self.collection_name}")
            else:
                logger.info(f"🔄 [CHROMADB] 使用现有空集合: {self.collection_name}")

            return True

        except Exception as e:
            logger.error(f"❌ [CHROMADB] 创建集合失败: {e}")
            return False

    def initialize(self) -> bool:
        """
        初始化ChromaDB客户端、加载模型并创建集合

        Returns:
            bool: 初始化是否成功
        """
        try:
            logger.info("🚀 [CHROMADB] 开始初始化向量数据库...")

            # 1. 初始化ChromaDB持久化客户端
            persist_directory = Path(DEFAULT_RAG_CONFIG.persist_directory)
            self.client = chromadb.PersistentClient(path=str(persist_directory))
            logger.success(
                f"✅ [CHROMADB] ChromaDB持久化客户端创建成功，数据目录: {persist_directory}"
            )

            # 2. 尝试加载已存在的集合
            if self._load_existing_collection():
                self.initialized = True
                logger.success("🎉 [CHROMADB] 向量数据库初始化完成（使用现有数据）！")
                return True

            # 3. 如果没有现有数据，创建新集合
            if self._create_new_collection():
                self.initialized = True
                logger.success("🎉 [CHROMADB] 向量数据库初始化完成（创建新集合）！")
                return True
            else:
                logger.error("❌ [CHROMADB] 创建新集合失败")
                return False

        except Exception as e:
            logger.error(f"❌ [CHROMADB] 初始化失败: {e}\n{traceback.format_exc()}")
            return False

    def close(self) -> None:
        """关闭数据库连接（清理资源），数据已持久化到磁盘"""
        try:
            if self.client and self.collection_name:
                # ChromaDB持久化客户端，数据已保存到磁盘
                logger.info("🔄 [CHROMADB] 数据库连接已清理，数据已持久化")
        except Exception as e:
            logger.warning(f"⚠️ [CHROMADB] 关闭数据库时出现警告: {e}")


############################################################################################################
def get_chroma_db() -> ChromaRAGDatabase:
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
            collection_name=DEFAULT_RAG_CONFIG.collection_name,
            collection_description=DEFAULT_RAG_CONFIG.description,
        )
        _chroma_db.initialize()
    return _chroma_db


############################################################################################################
def chromadb_clear_database() -> None:
    """
    完全清空ChromaDB持久化数据库
    注意：该方法会删除所有持久化数据，包括磁盘文件，请谨慎使用
    """
    import shutil

    # import os

    try:
        global _chroma_db

        # 如果有现有实例，先关闭
        if _chroma_db:
            _chroma_db.close()
            _chroma_db = None

        # 删除持久化数据目录
        persist_directory = Path(DEFAULT_RAG_CONFIG.persist_directory)
        if persist_directory.exists():
            shutil.rmtree(persist_directory)
            logger.warning(f"🗑️ [CHROMADB] 已删除持久化数据目录: {persist_directory}")
        else:
            logger.info(f"📁 [CHROMADB] 持久化数据目录不存在: {persist_directory}")

        logger.warning("🔄 [CHROMADB] ChromaDB持久化数据库已被完全清除")

    except Exception as e:
        logger.error(f"❌ 清空ChromaDB持久化数据库时发生错误: {e}")
        logger.info(f"💡 建议手动删除 {DEFAULT_RAG_CONFIG.persist_directory} 目录")
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
        knowledge_base: 要加载的知识库数据

    Returns:
        bool: 初始化是否成功
    """
    logger.info("🚀 [INIT] 开始初始化RAG系统...")

    try:
        # 1. 获取ChromaDB实例并初始化
        chroma_db = get_chroma_db()

        # 2. 检查是否需要加载知识库数据
        if chroma_db.collection and chroma_db.collection.count() == 0:
            logger.info("📚 [INIT] 集合为空，开始加载知识库数据...")
            
            # 3. 展开知识库加载逻辑（原 load_knowledge_base 方法的内容）
            try:
                logger.info("📚 [CHROMADB] 开始加载知识库数据...")

                if not chroma_db.collection:
                    logger.error("❌ [CHROMADB] 集合未初始化")
                    return False

                # 使用独立函数准备知识库数据
                embeddings_list, documents, metadatas, ids = (
                    prepare_knowledge_base_for_embedding(knowledge_base)
                )

                # 检查准备结果
                if not embeddings_list or not documents:
                    logger.error("❌ [CHROMADB] 知识库数据准备失败")
                    return False

                # 批量添加到ChromaDB
                logger.info("💾 [CHROMADB] 存储向量到数据库...")
                chroma_db.collection.add(
                    embeddings=embeddings_list,
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                )

                logger.success(
                    f"✅ [CHROMADB] 成功加载 {len(documents)} 个文档到向量数据库"
                )

                # 验证数据加载
                count = chroma_db.collection.count()
                logger.info(f"📊 [CHROMADB] 数据库中现有文档数量: {count}")

            except Exception as e:
                logger.error(f"❌ [CHROMADB] 知识库加载失败: {e}\n{traceback.format_exc()}")
                return False

        logger.success("🎉 [INIT] RAG系统初始化完成！")
        return True

    except Exception as e:
        logger.error(f"❌ [INIT] 初始化过程中发生错误: {e}\n{traceback.format_exc()}")
        logger.warning("⚠️ [INIT] 系统将回退到关键词匹配模式")
        return False


############################################################################################################
def semantic_search(query: str, top_k: int = 5) -> tuple[List[str], List[float]]:
    """
    执行全局语义搜索
    
    功能：
    1. 获取ChromaDB实例
    2. 获取嵌入模型
    3. 执行语义搜索
    4. 返回搜索结果

    Args:
        query: 用户查询文本
        top_k: 返回最相似的文档数量

    Returns:
        tuple: (检索到的文档列表, 相似度分数列表)
    """
    try:
        # 1. 获取ChromaDB实例
        chroma_db = get_chroma_db()
        
        if not chroma_db.initialized or not chroma_db.collection:
            logger.error("❌ [CHROMADB] 数据库未初始化")
            return [], []

        # 2. 获取全局嵌入模型实例
        embedding_model = get_embedding_model()
        if embedding_model is None:
            logger.error("❌ [CHROMADB] 嵌入模型未初始化")
            return [], []

        logger.info(f"🔍 [CHROMADB] 执行语义搜索: '{query}'")

        # 3. 计算查询向量
        query_embedding = embedding_model.encode([query])

        # 4. 在ChromaDB中执行向量搜索
        results = chroma_db.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )

        # 5. 提取结果
        documents = results["documents"][0] if results["documents"] else []
        distances = results["distances"][0] if results["distances"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []

        # 6. 将距离转换为相似度分数（距离越小，相似度越高）
        # 相似度 = 1 - 标准化距离
        if distances:
            max_distance = max(distances) if distances else 1.0
            similarity_scores = [
                max(0, 1 - (dist / max_distance)) for dist in distances
            ]
        else:
            similarity_scores = []

        logger.info(f"✅ [CHROMADB] 搜索完成，找到 {len(documents)} 个相关文档")

        # 7. 打印搜索结果详情（用于调试）
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


############################################################################################################


