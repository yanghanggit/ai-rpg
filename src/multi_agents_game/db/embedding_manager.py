"""
嵌入模型管理模块

负责：
1. 管理全局嵌入模型实例
2. 提供嵌入模型的单例访问
3. 准备知识库数据用于向量化
"""

import traceback
from typing import List, Optional, Dict, Mapping, Tuple, Sequence

from loguru import logger
from sentence_transformers import SentenceTransformer

from ..utils.model_loader import load_multilingual_model

############################################################################################################
# 全局嵌入模型实例
_embedding_model: Optional[SentenceTransformer] = None


############################################################################################################
def get_embedding_model() -> Optional[SentenceTransformer]:
    """
    获取全局嵌入模型实例（单例模式）

    Returns:
        Optional[SentenceTransformer]: 全局嵌入模型实例，如果加载失败则返回None
    """
    global _embedding_model
    if _embedding_model is None:
        logger.info("🔄 [EMBEDDING] 加载多语言语义模型...")
        _embedding_model = load_multilingual_model()
        if _embedding_model is None:
            logger.error("❌ [EMBEDDING] 多语言模型加载失败")
        else:
            logger.success("✅ [EMBEDDING] 多语言语义模型加载成功")
    return _embedding_model


############################################################################################################
def clear_embedding_model() -> None:
    """
    清理全局嵌入模型实例
    """
    global _embedding_model
    _embedding_model = None
    logger.info("🔄 [EMBEDDING] 全局嵌入模型实例已清理")


############################################################################################################
def prepare_knowledge_base_for_embedding(
    knowledge_base: Dict[str, List[str]],
) -> Tuple[
    List[Sequence[float]],
    List[str],
    List[Mapping[str, str | int | float | bool | None]],
    List[str],
]:
    """
    准备知识库数据用于向量化和存储

    Args:
        knowledge_base: 知识库数据，格式为 {category: [documents]}

    Returns:
        Tuple: (embeddings, documents, metadatas, ids) - collection.add()方法的参数
    """
    try:
        logger.info("🔄 [PREPARE] 开始准备知识库数据...")

        # 获取全局嵌入模型实例
        embedding_model = get_embedding_model()
        if embedding_model is None:
            logger.error("❌ [PREPARE] 嵌入模型未初始化")
            return [], [], [], []

        # 准备文档数据
        documents: List[str] = []
        metadatas: List[Mapping[str, str | int | float | bool | None]] = []
        ids: List[str] = []

        doc_id = 0
        for category, docs in knowledge_base.items():
            for doc in docs:
                documents.append(doc)
                metadatas.append({"category": category, "doc_id": doc_id})
                ids.append(f"{category}_{doc_id}")
                doc_id += 1

        logger.info(f"📊 [PREPARE] 准备向量化 {len(documents)} 个文档...")

        # 使用SentenceTransformer计算向量嵌入
        logger.info("🔄 [PREPARE] 计算文档向量嵌入...")
        embeddings = embedding_model.encode(documents)

        # 转换为列表格式（ChromaDB要求）
        embeddings_list = embeddings.tolist()

        logger.success(f"✅ [PREPARE] 成功准备 {len(documents)} 个文档的嵌入数据")

        return embeddings_list, documents, metadatas, ids

    except Exception as e:
        logger.error(f"❌ [PREPARE] 准备知识库数据失败: {e}\n{traceback.format_exc()}")
        return [], [], [], []


############################################################################################################
