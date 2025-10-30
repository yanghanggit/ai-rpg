"""
嵌入模型管理模块

负责：
1. 管理全局嵌入模型实例
2. 提供嵌入模型的单例访问
3. 准备知识库数据用于向量化
"""

from typing import Optional

from loguru import logger
from sentence_transformers import SentenceTransformer

from .model_loader import load_multilingual_model

############################################################################################################
# 全局嵌入模型实例
_sentence_transformer: Optional[SentenceTransformer] = None


############################################################################################################
def get_embedding_model() -> Optional[SentenceTransformer]:
    """
    获取全局嵌入模型实例（单例模式）

    Returns:
        Optional[SentenceTransformer]: 全局嵌入模型实例，如果加载失败则返回None
    """
    global _sentence_transformer
    if _sentence_transformer is None:
        logger.info("🔄 [EMBEDDING] 加载多语言语义模型...")
        _sentence_transformer = load_multilingual_model()
        if _sentence_transformer is None:
            logger.error("❌ [EMBEDDING] 多语言模型加载失败")
        else:
            logger.success("✅ [EMBEDDING] 多语言语义模型加载成功")
    return _sentence_transformer


############################################################################################################
