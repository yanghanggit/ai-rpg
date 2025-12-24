"""ChromaDB 客户端管理模块

该模块提供了 ChromaDB 向量数据库的客户端实例和相关操作方法，
主要用于 AI RPG 系统中的向量存储和检索功能。

Typical usage example:
    # 获取默认集合
    collection = get_default_collection()

    # 重置客户端（清除所有数据）
    reset_client()
"""

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from loguru import logger

# 全局 ChromaDB 客户端实例
# 使用持久化客户端，数据会保存在本地文件系统中
chroma_client: ClientAPI = chromadb.PersistentClient()
logger.info(f"ChromaDB Settings: {chroma_client.get_settings().persist_directory}")


##################################################################################################################
def reset_client() -> None:
    """重置 ChromaDB 客户端，清除所有数据和缓存

    该函数会执行以下操作：
    1. 删除客户端中的所有集合（Collection）
    2. 清理系统缓存

    警告：
        这是一个破坏性操作，会永久删除所有存储的向量数据！
        在生产环境中使用时请格外小心。

    Raises:
        Exception: 当删除集合过程中发生错误时，会记录错误日志但不会中断程序

    Example:
        >>> reset_client()  # 清除所有数据
        ✅ [CHROMADB] 已清理系统缓存
    """
    try:
        # 获取并删除所有现有集合
        connections = chroma_client.list_collections()
        for conn in connections:
            chroma_client.delete_collection(name=conn.name)
            logger.warning(f"🗑️ [CHROMADB] 已删除集合: {conn.name}")

        # 清理系统缓存，释放内存资源
        chroma_client.clear_system_cache()
        logger.info(f"✅ [CHROMADB] 已清理系统缓存")
    except Exception as e:
        logger.error(f"❌ [CHROMADB] 删除集合时出错: {e}")


##################################################################################################################
def get_default_collection() -> Collection:
    """获取或创建默认的向量集合

    该函数会返回名为 'default_collection' 的集合。
    如果集合不存在，会自动创建一个新的集合。

    Returns:
        Collection: ChromaDB 集合对象，用于存储和检索向量数据

    Note:
        这是 AI RPG 系统的默认集合，用于存储游戏相关的向量数据，
        如角色描述、场景信息、对话历史等的向量表示。

    Example:
        >>> collection = get_default_collection()
        >>> collection.add(
        ...     documents=["这是一个游戏角色的描述"],
        ...     ids=["character_001"]
        ... )
    """
    return chroma_client.get_or_create_collection(
        name="default_collection",
        metadata={"description": "Default collection for AI RPG system!"},
    )


##################################################################################################################
def get_private_knowledge_collection() -> Collection:
    """获取或创建角色私有知识库的专用集合

    该函数会返回名为 'private_knowledge_collection' 的集合。
    如果集合不存在，会自动创建一个新的集合。

    与 default_collection 的区别：
    - default_collection: 存储公共知识（世界设定、规则等）
    - private_knowledge_collection: 存储角色私有知识（记忆、秘密等）

    Returns:
        Collection: ChromaDB 集合对象，专门用于存储角色私有知识

    Note:
        这是角色私有知识的专用存储空间，通过 metadata 中的 character_name
        实现不同角色之间的隔离。每个角色只能访问自己的私有知识。

    Example:
        >>> collection = get_private_knowledge_collection()
        >>> collection.add(
        ...     documents=["我是法师奥露娜"],
        ...     metadatas=[{"character_name": "角色.法师.奥露娜"}],
        ...     ids=["角色.法师.奥露娜_private_0"]
        ... )
        >>> # 查询时使用 where 过滤
        >>> results = collection.get(where={"character_name": "角色.法师.奥露娜"})
    """
    return chroma_client.get_or_create_collection(
        name="private_knowledge_collection",
        metadata={
            "description": "Private knowledge collection for character isolation"
        },
    )


##################################################################################################################
