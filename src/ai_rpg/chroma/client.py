"""ChromaDB 客户端管理模块

该模块提供 RAG 系统的向量数据库客户端和集合管理功能：
1. 持久化客户端实例 - 向量数据保存在本地文件系统
2. 默认集合管理 - 提供全局共享的向量集合
3. 客户端重置 - 用于开发环境初始化

核心功能：
- chroma_client: 全局持久化客户端实例
- get_default_collection: 获取或创建默认向量集合
- reset_client: 清空所有数据（仅用于开发环境）

Typical usage example:
    # 获取默认集合用于向量存储
    collection = get_default_collection()

    # 开发环境初始化：清除所有数据
    reset_client()
"""

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from loguru import logger

# 全局 ChromaDB 客户端实例
# 使用持久化客户端，数据会保存在本地文件系统中
chroma_client: ClientAPI = chromadb.PersistentClient()
# logger.info(f"ChromaDB Settings: {chroma_client.get_settings().persist_directory}")


##################################################################################################################
def reset_client() -> None:
    """重置 ChromaDB 客户端，清除所有向量数据（仅用于开发环境）

    功能：
    1. 删除所有集合（Collection）
    2. 清理系统缓存

    警告：
        破坏性操作！会永久删除所有向量数据。
        仅用于开发环境初始化，生产环境禁用。

    Raises:
        Exception: 删除集合失败时记录错误但不中断程序

    Example:
        >>> reset_client()  # 开发环境初始化
        ✅ [VECTOR] 已清理系统缓存
    """
    try:
        # 获取并删除所有现有集合
        connections = chroma_client.list_collections()
        for conn in connections:
            chroma_client.delete_collection(name=conn.name)
            logger.warning(f"🗑️ [VECTOR] 已删除集合: {conn.name}")

        # 清理系统缓存，释放内存资源
        chroma_client.clear_system_cache()
        logger.info(f"✅ [VECTOR] 已清理系统缓存")
    except Exception as e:
        logger.error(f"❌ [VECTOR] 删除集合时出错: {e}")


##################################################################################################################
def get_default_collection() -> Collection:
    """获取或创建默认向量集合

    功能：
    1. 返回全局共享的向量集合实例
    2. 首次调用时自动创建集合
    3. 后续调用复用已存在的集合

    集合配置：
    - 名称: "default_collection"
    - 相似度度量: 余弦相似度（cosine）
    - 用途: RAG 系统的全局知识库存储

    Returns:
        Collection: ChromaDB 集合实例，用于向量存储和检索

    Example:
        >>> collection = get_default_collection()
        >>> collection.add(embeddings=[...], documents=[...])
    """
    return chroma_client.get_or_create_collection(
        name="default_collection",
        metadata={
            "description": "default collection",
            "hnsw:space": "cosine",  # 使用余弦相似度而不是L2距离
        },
    )


##################################################################################################################
def get_custom_collection(name: str) -> Collection:
    """获取或创建自定义名称的向量集合

    功能：
    1. 根据传入的名称返回对应的向量集合实例
    2. 首次调用时自动创建集合
    3. 后续调用复用已存在的集合

    集合配置：
    - 名称: 由参数 name 指定
    - 相似度度量: 余弦相似度（cosine）
    - 用途: 可用于不同模块或功能的独立知识库存储

    Args:
        name (str): 自定义集合名称

    Returns:
        Collection: ChromaDB 集合实例，用于向量存储和检索

    Example:
        >>> user_collection = get_custom_collection("user_123_collection")
        >>> user_collection.add(embeddings=[...], documents=[...])
    """
    return chroma_client.get_or_create_collection(
        name=name,
        metadata={
            "description": f"custom collection: {name}",
            "hnsw:space": "cosine",  # 使用余弦相似度而不是L2距离
        },
    )


##################################################################################################################
