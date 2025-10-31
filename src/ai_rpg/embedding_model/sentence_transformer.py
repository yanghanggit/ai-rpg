"""
嵌入模型管理模块

负责：
1. 管理全局嵌入模型实例
2. 提供嵌入模型的单例访问
3. 准备知识库数据用于向量化
"""

from .config import cache_path
from loguru import logger
from sentence_transformers import SentenceTransformer

try:
    multilingual_model: SentenceTransformer = SentenceTransformer(
        str(cache_path("paraphrase-multilingual-MiniLM-L12-v2"))
    )

    logger.info("✅ [EMBEDDING] 预加载多语言模型成功")
except Exception as e:
    logger.error(f"❌ [EMBEDDING] 预加载多语言模型失败: {e}")
    assert False, "预加载多语言模型失败"
