"""
嵌入模型管理模块
"""

from loguru import logger
from sentence_transformers import SentenceTransformer
from pathlib import Path

try:

    cache_model_path = (
        Path(".sentence_transformers") / "paraphrase-multilingual-MiniLM-L12-v2"
    )
    if not cache_model_path.exists():
        logger.warning(
            f"⚠️ [EMBEDDING] 模型缓存目录不存在: {cache_model_path}，请先运行 scripts/download_sentence_transformers_models.py 下载模型"
        )
        raise FileNotFoundError(
            f"模型缓存目录不存在: {cache_model_path}，请先运行 scripts/download_sentence_transformers_models.py 下载模型"
        )

    # fix_mistral_regex=False：该模型是 BERT 分词器，transformers>=4.57.3 对本地分词器一律
    # 误报 Mistral 分词正则告警（与模型实际类型无关），显式声明以避免误报且不套用不相关的 Mistral 补丁
    # 全局嵌入模型实例：将文本编码为向量，供 RAG 语义检索使用
    embedding_model: SentenceTransformer = SentenceTransformer(
        str(cache_model_path), tokenizer_kwargs={"fix_mistral_regex": False}
    )
    logger.info("✅ [EMBEDDING] 预加载多语言模型成功")

except Exception as e:
    logger.error(f"❌ [EMBEDDING] 预加载多语言模型失败: {e}")
    raise e
