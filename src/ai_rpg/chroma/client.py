from pathlib import Path
import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from loguru import logger
import shutil

chroma_client: ClientAPI = chromadb.PersistentClient()
logger.info(f"ChromaDB Settings: {chroma_client.get_settings().persist_directory}")


def clear_client() -> None:

    global chroma_client

    # 获取 ChromaDB 设置，然后删除持久化目录！
    settings = chroma_client.get_settings()
    logger.info(f"ChromaDB Settings: {settings.persist_directory}")
    persist_directory = Path(settings.persist_directory)

    # 清理系统缓存
    chroma_client.clear_system_cache()

    # 删除持久化目录
    if persist_directory.exists():
        shutil.rmtree(persist_directory)
        logger.warning(f"🗑️ [CHROMADB] 已删除持久化数据目录: {persist_directory}")
    else:
        logger.info(f"📁 [CHROMADB] 持久化数据目录不存在: {persist_directory}")

    # 重新创建客户端实例以避免权限问题
    chroma_client = chromadb.PersistentClient()
    logger.info(
        f"🔄 [CHROMADB] 重新创建客户端，数据目录: {chroma_client.get_settings().persist_directory}"
    )


##################################################################################################################
def get_default_collection() -> Collection:
    global chroma_client

    return chroma_client.get_or_create_collection(
        name="default_collection",
        metadata={"description": "Default collection for AI RPG system!"},
    )


##################################################################################################################
