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
from typing import Any, Dict, List, Mapping, Tuple
from loguru import logger
from chromadb.api.models.Collection import Collection
from sentence_transformers import SentenceTransformer


############################################################################################################
def add_documents_to_vector_db(
    collection: Collection,
    embedding_model: SentenceTransformer,
    documents: Dict[str, List[str]] | List[str],
    owner: str | None = None,
    skip_if_exists: bool = False,
) -> bool:
    """
    统一的文档加载函数，支持公共知识和私有知识两种模式

    功能：
    1. 将文档向量化并存储到 ChromaDB
    2. 根据输入类型自动识别加载模式

    Args:
        collection: ChromaDB Collection 实例
        embedding_model: SentenceTransformer 嵌入模型实例
        documents: 文档数据
            - Dict[str, List[str]]: 公共知识模式，格式为 {category: [docs]}
            - List[str]: 私有知识模式，需同时提供 owner
        owner: 所有者标识（私有知识模式必需）。
               格式建议："游戏名.角色名" 或 "游戏名.用户ID"，用于多游戏场景隔离
        skip_if_exists: 如果集合已有数据是否跳过加载（默认False）

    Returns:
        bool: 加载是否成功

    Examples:
        # 公共知识模式
        add_documents_to_vector_db(
            collection=collection,
            embedding_model=model,
            documents={"世界观": ["魔法世界"], "规则": ["战斗规则"]},
            skip_if_exists=True
        )

        # 私有知识模式（带游戏名前缀）
        add_documents_to_vector_db(
            collection=collection,
            embedding_model=model,
            documents=["我是法师奥露娜", "我在星辉学院学习"],
            owner="魔法学院RPG.角色.法师.奥露娜"
        )
    """
    try:
        # 1. 验证参数
        if not collection:
            logger.error("❌ [LOAD] Collection 未初始化")
            return False

        # 检查是否跳过已有数据
        if skip_if_exists and collection.count() > 0:
            logger.info(f"📚 [LOAD] 集合已有 {collection.count()} 个文档，跳过加载")
            return True

        # 2. 区分加载模式
        is_private_mode = isinstance(documents, list)

        # 准备数据结构（避免类型重定义错误）
        doc_list: List[str] = []
        metadata_list: List[Mapping[str, str | int | float | bool | None]] = []
        id_list: List[str] = []

        if is_private_mode:
            # 私有知识模式
            if not owner:
                logger.error("❌ [LOAD] 私有知识模式需要提供 owner")
                return False

            if not documents:
                logger.warning(f"⚠️  [LOAD] 所有者 {owner} 没有私有知识，跳过加载")
                return True

            logger.info(f"🔐 [LOAD] 为 {owner} 加载 {len(documents)} 条私有知识...")

            for i, doc in enumerate(documents):
                doc_list.append(doc)
                metadata_list.append(
                    {
                        "type": "private",
                        "character_name": owner,
                        "doc_id": i,
                    }
                )
                id_list.append(f"{owner}_private_{i}")

        else:
            # 知识库模式
            logger.info("🚀 [LOAD] 开始加载知识库数据...")

            # 类型缩窄：确保 documents 是字典类型
            assert isinstance(documents, dict), "公共知识模式需要字典格式"

            doc_id = 0
            for category, docs in documents.items():
                for doc in docs:
                    doc_list.append(doc)
                    metadata_list.append(
                        {"type": "public", "category": category, "doc_id": doc_id}
                    )
                    id_list.append(f"{category}_{doc_id}")
                    doc_id += 1

            if not doc_list:
                logger.error("❌ [LOAD] 知识库数据准备失败")
                return False

        # 3. 计算向量嵌入（公共知识和私有知识都需要）
        logger.info("🔄 [LOAD] 计算文档向量嵌入...")
        embeddings = embedding_model.encode(doc_list)
        embeddings_list = embeddings.tolist()

        # 4. 添加到 ChromaDB
        logger.info("💾 [LOAD] 存储向量到数据库...")
        collection.add(
            embeddings=embeddings_list,
            documents=doc_list,
            metadatas=metadata_list,  # type: ignore[arg-type]
            ids=id_list,
        )

        logger.success(f"✅ [LOAD] 成功加载 {len(doc_list)} 个文档")
        return True

    except Exception as e:
        context = f"所有者 {owner}" if owner else "公共知识库"
        logger.error(f"❌ [LOAD] {context} 加载失败: {e}\n{traceback.format_exc()}")
        return False


############################################################################################################
def search_similar_documents(
    query: str,
    collection: Collection,
    embedding_model: SentenceTransformer,
    top_k: int = 5,
    owner: str | None = None,
) -> Tuple[List[str], List[float]]:
    """
    执行语义搜索（统一查询公共知识 + 所有者私有知识）

    功能：
    1. 计算查询向量
    2. 执行向量搜索
    3. 返回搜索结果

    Args:
        query: 用户查询文本
        collection: ChromaDB Collection 实例
        embedding_model: SentenceTransformer 嵌入模型实例
        top_k: 返回最相似的文档数量
        owner: 所有者标识（可选）。如果提供，将查询公共知识 + 该所有者的私有知识。
               格式建议："游戏名.角色名" 来实现多游戏场景的知识隔离

    Returns:
        tuple: (检索到的文档列表, 相似度分数列表)

    Example:
        # 查询公共知识 + 所有者私有知识（使用游戏名前缀）
        docs, scores = search_similar_documents(
            query="魔法系统是什么",
            collection=get_default_collection(),
            embedding_model=multilingual_model,
            owner="魔法学院RPG.角色.法师.奥露娜",
            top_k=5
        )
    """
    try:
        # 1. 验证集合状态
        if not collection:
            logger.error("❌ [CHROMADB] 集合未初始化")
            return [], []

        logger.info(
            f"🔍 [CHROMADB] 执行语义搜索: '{query}'"
            + (f" (所有者: {owner})" if owner else "")
        )

        # 2. 计算查询向量
        query_embedding = embedding_model.encode([query])

        # 3. 构建 where 条件（查询公共知识 + 所有者私有知识）
        where_clause: Any = None
        if owner:
            where_clause = {"$or": [{"type": "public"}, {"character_name": owner}]}
            logger.debug(f"📋 [CHROMADB] 查询范围: 公共知识 + {owner} 的私有知识")
        else:
            logger.debug("📋 [CHROMADB] 查询范围: 所有知识")

        # 4. 在ChromaDB中执行向量搜索
        results = collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=top_k,
            where=where_clause,
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
            doc_type = metadata.get("type", "unknown")
            doc_info = f"类型: {doc_type}"
            if doc_type == "public":
                doc_info += f", 类别: {metadata.get('category', 'unknown')}"
            elif doc_type == "private":
                doc_info += f", 角色: {metadata.get('character_name', 'unknown')}"
            logger.debug(
                f"  📄 [{i+1}] 相似度: {score:.3f}, {doc_info}, 内容: {doc[:50]}..."
            )

        return documents, similarity_scores

    except Exception as e:
        logger.error(f"❌ [CHROMADB] 语义搜索失败: {e}\n{traceback.format_exc()}")
        return [], []


############################################################################################################
