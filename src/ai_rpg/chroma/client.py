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
    """获取或创建统一的向量集合

    该函数会返回名为 'default_collection' 的集合。
    如果集合不存在，会自动创建一个新的集合。

    Returns:
        Collection: ChromaDB 集合对象，用于存储和检索向量数据

    Note:
        这是 AI RPG 系统的统一集合，同时存储：
        1. 公共知识（世界设定、规则等） - metadata: {"type": "public", "category": "..."}
        2. 私有知识（用户记忆、秘密等） - metadata: {"type": "private", "character_name": "..."}

        通过 metadata 中的 type 和 character_name 实现数据隔离和过滤。
        character_name 使用 "游戏名.实体名" 格式（如 "魔法学院RPG.角色.法师.奥露娜"）
        来实现多游戏场景的知识隔离。

    Example:
        >>> collection = get_default_collection()
        >>> # 添加公共知识
        >>> collection.add(
        ...     documents=["这是世界设定"],
        ...     metadatas=[{"type": "public", "category": "世界观"}],
        ...     ids=["世界观_0"]
        ... )
        >>> # 添加私有知识（以角色为例，使用游戏名前缀）
        >>> collection.add(
        ...     documents=["我是法师奥露娜"],
        ...     metadatas=[{"type": "private", "character_name": "魔法学院RPG.角色.法师.奥露娜"}],
        ...     ids=["魔法学院RPG.角色.法师.奥露娜_private_0"]
        ... )
        >>> # 查询时使用 where 过滤（查询公共 + 特定游戏特定角色的私有知识）
        >>> results = collection.query(
        ...     query_embeddings=[[...]],
        ...     where={"$or": [{"type": "public"}, {"character_name": "魔法学院RPG.角色.法师.奥露娜"}]}
        ... )
    """
    return chroma_client.get_or_create_collection(
        name="default_collection",
        metadata={
            "description": "Unified collection for AI RPG system (public + private knowledge)"
        },
    )


##################################################################################################################
