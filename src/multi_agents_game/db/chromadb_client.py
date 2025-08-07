import traceback
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from loguru import logger

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
