"""
RAG操作模块

此模块提供RAG（检索增强生成）系统的核心操作功能：
1. 初始化RAG系统 - 设置向量数据库和嵌入模型
2. 语义搜索 - 基于查询文本检索相关文档

功能：
- initialize_rag_system: 初始化整个RAG系统，包括向量数据库和知识库加载
- semantic_search: 执行语义搜索，返回最相关的文档和相似度分数
"""

import traceback
from typing import Dict, List, Mapping, Sequence, Tuple

from loguru import logger

from .chromadb_client import get_chroma_db
from ..embedding_model.sentence_transformer_embedding_model import (
    get_embedding_model,
)


############################################################################################################
def initialize_knowledge_base_embeddings(
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
def initialize_rag_system(knowledge_base: Dict[str, List[str]]) -> bool:
    """
    初始化RAG系统

    功能：
    1. 初始化ChromaDB向量数据库
    2. 加载SentenceTransformer模型
    3. 将知识库数据向量化并存储
    4. 验证系统就绪状态

    Args:
        knowledge_base: 要加载的知识库数据

    Returns:
        bool: 初始化是否成功
    """
    logger.info("🚀 [INIT] 开始初始化RAG系统...")

    try:
        # 1. 获取ChromaDB实例并初始化
        chroma_db = get_chroma_db()

        # 2. 检查是否需要加载知识库数据
        if chroma_db.collection and chroma_db.collection.count() == 0:
            logger.info("📚 [INIT] 集合为空，开始加载知识库数据...")

            # 3. 展开知识库加载逻辑（原 load_knowledge_base 方法的内容）
            try:
                logger.info("📚 [CHROMADB] 开始加载知识库数据...")

                if not chroma_db.collection:
                    logger.error("❌ [CHROMADB] 集合未初始化")
                    return False

                # 使用独立函数准备知识库数据
                embeddings_list, documents, metadatas, ids = (
                    initialize_knowledge_base_embeddings(knowledge_base)
                )

                # 检查准备结果
                if not embeddings_list or not documents:
                    logger.error("❌ [CHROMADB] 知识库数据准备失败")
                    return False

                # 批量添加到ChromaDB
                logger.info("💾 [CHROMADB] 存储向量到数据库...")
                chroma_db.collection.add(
                    embeddings=embeddings_list,
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                )

                logger.success(
                    f"✅ [CHROMADB] 成功加载 {len(documents)} 个文档到向量数据库"
                )

                # 验证数据加载
                count = chroma_db.collection.count()
                logger.info(f"📊 [CHROMADB] 数据库中现有文档数量: {count}")

            except Exception as e:
                logger.error(
                    f"❌ [CHROMADB] 知识库加载失败: {e}\n{traceback.format_exc()}"
                )
                return False

        logger.success("🎉 [INIT] RAG系统初始化完成！")
        return True

    except Exception as e:
        logger.error(f"❌ [INIT] 初始化过程中发生错误: {e}\n{traceback.format_exc()}")
        logger.warning("⚠️ [INIT] 系统将回退到关键词匹配模式")
        return False


############################################################################################################
def rag_semantic_search(query: str, top_k: int = 5) -> tuple[List[str], List[float]]:
    """
    执行全局语义搜索

    功能：
    1. 获取ChromaDB实例
    2. 获取嵌入模型
    3. 执行语义搜索
    4. 返回搜索结果

    Args:
        query: 用户查询文本
        top_k: 返回最相似的文档数量

    Returns:
        tuple: (检索到的文档列表, 相似度分数列表)
    """
    try:
        # 1. 获取ChromaDB实例
        chroma_db = get_chroma_db()

        if not chroma_db.initialized or not chroma_db.collection:
            logger.error("❌ [CHROMADB] 数据库未初始化")
            return [], []

        # 2. 获取全局嵌入模型实例
        embedding_model = get_embedding_model()
        if embedding_model is None:
            logger.error("❌ [CHROMADB] 嵌入模型未初始化")
            return [], []

        logger.info(f"🔍 [CHROMADB] 执行语义搜索: '{query}'")

        # 3. 计算查询向量
        query_embedding = embedding_model.encode([query])

        # 4. 在ChromaDB中执行向量搜索
        results = chroma_db.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )

        # 5. 提取结果
        documents = results["documents"][0] if results["documents"] else []
        distances = results["distances"][0] if results["distances"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []

        # 6. 将距离转换为相似度分数（距离越小，相似度越高）
        # 相似度 = 1 - 标准化距离
        if distances:
            max_distance = max(distances) if distances else 1.0
            similarity_scores = [
                max(0, 1 - (dist / max_distance)) for dist in distances
            ]
        else:
            similarity_scores = []

        logger.info(f"✅ [CHROMADB] 搜索完成，找到 {len(documents)} 个相关文档")

        # 7. 打印搜索结果详情（用于调试）
        for i, (doc, score, metadata) in enumerate(
            zip(documents, similarity_scores, metadatas)
        ):
            logger.debug(
                f"  📄 [{i+1}] 相似度: {score:.3f}, 类别: {metadata.get('category', 'unknown')}, 内容: {doc[:50]}..."
            )

        return documents, similarity_scores

    except Exception as e:
        logger.error(f"❌ [CHROMADB] 语义搜索失败: {e}\n{traceback.format_exc()}")
        return [], []


############################################################################################################
