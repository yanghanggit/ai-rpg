"""
RAG 知识检索模块

此模块提供 RAG（检索增强生成）系统的文档管理和语义搜索功能：
1. 文档加载 - 将文档向量化并存储到 ChromaDB
2. 语义搜索 - 基于向量相似度检索最相关的文档

核心功能：
- add_documents: 加载文档到向量数据库（纯工具函数，不含业务逻辑）
- search_documents: 执行语义搜索，返回最相关的文档和相似度分数
"""

import traceback
from typing import Any, Dict, List, Tuple
from loguru import logger
from chromadb.api.models.Collection import Collection
from sentence_transformers import SentenceTransformer


############################################################################################################
def add_documents(
    collection: Collection,
    embedding_model: SentenceTransformer,
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    ids: List[str],
) -> bool:
    """
    加载文档到向量数据库（纯工具函数）

    功能：
    1. 将文档向量化并存储到 ChromaDB
    2. 不包含业务逻辑，由调用方准备所有数据

    Args:
        collection: ChromaDB Collection 实例
        embedding_model: SentenceTransformer 嵌入模型实例
        documents: 文档列表
        metadatas: 元数据列表，与 documents 一一对应
        ids: 文档ID列表，与 documents 一一对应

    Returns:
        bool: 加载是否成功

    Example:
        add_documents(
            collection=collection,
            embedding_model=model,
            documents=["魔法世界", "战斗规则"],
            metadatas=[{"category": "世界观"}, {"category": "规则"}],
            ids=["worldview_0", "rule_1"]
        )
    """
    try:
        # 1. 验证参数
        if not collection:
            logger.error("❌ [LOAD] Collection 未初始化")
            return False

        if not documents:
            logger.warning("⚠️  [LOAD] 文档数据为空，跳过加载")
            return True

        # 2. 验证数据长度一致性
        if len(documents) != len(metadatas) or len(documents) != len(ids):
            logger.error(
                f"❌ [LOAD] 数据长度不一致: documents={len(documents)}, metadatas={len(metadatas)}, ids={len(ids)}"
            )
            return False

        # 3. 计算向量嵌入
        logger.info(f"🚀 [LOAD] 开始加载 {len(documents)} 个文档...")
        logger.info("🔄 [LOAD] 计算文档向量嵌入...")
        embeddings = embedding_model.encode(documents).tolist()

        # 4. 存储到 ChromaDB
        logger.info("💾 [LOAD] 存储向量到数据库...")
        collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,  # type: ignore[arg-type]
            ids=ids,
        )

        logger.success(f"✅ [LOAD] 成功加载 {len(documents)} 个文档")
        return True

    except Exception as e:
        logger.error(f"❌ [LOAD] 文档加载失败: {e}\n{traceback.format_exc()}")
        return False


############################################################################################################
def search_documents(
    query: str,
    collection: Collection,
    embedding_model: SentenceTransformer,
    top_k: int = 5,
) -> Tuple[List[str], List[float]]:
    """
    执行语义搜索，查询公共知识库

    功能：
    1. 计算查询向量
    2. 执行向量搜索
    3. 返回搜索结果

    Args:
        query: 用户查询文本
        collection: ChromaDB Collection 实例
        embedding_model: SentenceTransformer 嵌入模型实例
        top_k: 返回最相似的文档数量

    Returns:
        tuple: (检索到的文档列表, 相似度分数列表)

    Example:
        docs, scores = search_documents(
            query="魔法系统是什么",
            collection=get_default_collection(),
            embedding_model=multilingual_model,
            top_k=5
        )
    """
    try:
        # 1. 验证集合状态
        if not collection:
            logger.error("❌ [SEARCH] 集合未初始化")
            return [], []

        logger.info(f"🔍 [SEARCH] 执行语义搜索: '{query}'")

        # 2. 计算查询向量
        query_vector = embedding_model.encode([query])

        # 3. 执行向量搜索
        results = collection.query(
            query_embeddings=query_vector.tolist(),
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )

        # 4. 提取结果
        documents = results["documents"][0] if results["documents"] else []
        cosine_distances = results["distances"][0] if results["distances"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []

        # 5. 将余弦距离转换为相似度分数
        # ChromaDB 使用余弦距离（cosine distance = 1 - cosine_similarity）
        # 余弦距离范围是 [0, 2]，我们将其映射到 [0, 1] 范围
        # similarity = 1 - distance/2
        if cosine_distances:
            logger.debug(
                f"📏 [SEARCH] 原始余弦距离: {[f'{d:.4f}' for d in cosine_distances[:3]]}"
            )
            similarity_scores = [
                max(0.0, min(1.0, 1.0 - dist / 2.0)) for dist in cosine_distances
            ]
            logger.debug(
                f"📊 [SEARCH] 转换后相似度: {[f'{s:.4f}' for s in similarity_scores[:3]]}"
            )
        else:
            similarity_scores = []

        logger.info(f"✅ [SEARCH] 搜索完成，找到 {len(documents)} 个相关文档")

        # 6. 打印搜索结果详情（用于调试）
        for i, (doc, score, metadata) in enumerate(
            zip(documents, similarity_scores, metadatas)
        ):
            # 通用打印：metadata 有什么就显示什么
            metadata_str = ", ".join(f"{k}: {v}" for k, v in metadata.items())
            logger.debug(
                f"  📄 [{i+1}] 相似度: {score:.3f} | {metadata_str} | 内容: {doc[:50]}..."
            )

        return documents, similarity_scores

    except Exception as e:
        logger.error(f"❌ [SEARCH] 语义搜索失败: {e}\n{traceback.format_exc()}")
        return [], []


############################################################################################################
