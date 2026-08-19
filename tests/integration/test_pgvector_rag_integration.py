#!/usr/bin/env python3
"""
pgvector RAG系统集成测试

用于验证基于 pgvector 的 RAG 系统是否能正常初始化和运行

测试策略：
1. 创建独立的测试知识库（与主系统隔离）
2. 使用独立的 collection 名称（不影响主系统）
3. 测试所有核心 RAG 功能
"""

from typing import Dict, Generator, List, Tuple
import pytest
from loguru import logger

from src.ai_rpg.rag import add_documents, search_documents, delete_collection
from src.ai_rpg.pgsql.client import pgsql_ensure_database_tables
from src.ai_rpg.embedding_model import embedding_model


# ============================================================================
# 测试专用知识库（独立于游戏主系统）
# ============================================================================
TEST_KNOWLEDGE_BASE: Dict[str, List[str]] = {
    "编程语言": [
        "Python是一种高级编程语言，以其简洁的语法和强大的标准库而闻名",
        "JavaScript是Web开发的核心语言，可以在浏览器和服务器端运行",
        "Rust是一种系统编程语言，强调内存安全和并发性能",
        "Go语言由Google开发，专注于简洁性和高效的并发处理",
    ],
    "数据库": [
        "PostgreSQL是一个功能强大的开源关系型数据库系统",
        "MongoDB是一个流行的NoSQL文档数据库，使用JSON格式存储数据",
        "Redis是一个内存数据库，常用于缓存和消息队列",
        "pgvector是PostgreSQL的扩展，专门用于存储和检索嵌入向量",
    ],
    "AI技术": [
        "机器学习是人工智能的一个分支，通过数据训练模型来做出预测",
        "深度学习使用神经网络模拟人脑的学习过程",
        "自然语言处理技术使计算机能够理解和生成人类语言",
        "RAG系统结合检索和生成技术，提供更准确的AI响应",
    ],
}

# 测试专用 collection 名称
TEST_COLLECTION_NAME = "test_rag_collection"


# ============================================================================
# 辅助函数
# ============================================================================
def _init_test_rag_system() -> bool:
    """初始化测试专用的 RAG 系统"""
    documents_list: List[str] = []
    metadatas_list: List[Dict[str, str]] = []

    for category, docs in TEST_KNOWLEDGE_BASE.items():
        for doc in docs:
            documents_list.append(doc)
            metadatas_list.append({"category": category})

    logger.info(f"开始加载测试知识库，共 {len(documents_list)} 个文档")
    return add_documents(
        collection=TEST_COLLECTION_NAME,
        embedding_model=embedding_model,
        documents=documents_list,
        metadatas=metadatas_list,
    )


def _test_search(query: str, top_k: int = 5) -> Tuple[List[str], List[float]]:
    """测试专用的语义搜索函数"""
    return search_documents(query, TEST_COLLECTION_NAME, embedding_model, top_k)


@pytest.fixture(scope="module", autouse=True)
def _setup_test_collection() -> Generator[None, None, None]:
    """确保表存在、清空测试 collection 后加载测试知识库，测试结束后清理"""
    pgsql_ensure_database_tables()
    delete_collection(TEST_COLLECTION_NAME)
    success = _init_test_rag_system()
    assert success, "pgvector RAG系统初始化失败"
    yield
    delete_collection(TEST_COLLECTION_NAME)


@pytest.mark.integration
@pytest.mark.database
class TestPgvectorRAGIntegration:
    """pgvector RAG系统集成测试类"""

    def test_pgvector_rag_initialization(self) -> None:
        """测试 pgvector RAG 系统初始化"""
        logger.info("🧪 开始测试 pgvector RAG 系统初始化...")

        docs, scores = _test_search("Python", top_k=10)
        expected_count = sum(len(docs) for docs in TEST_KNOWLEDGE_BASE.values())
        assert len(docs) == min(
            10, expected_count
        ), f"文档数量不符: 期望至多{min(10, expected_count)}, 实际{len(docs)}"

        logger.success(f"🎉 pgvector RAG 系统初始化测试通过！")

    def test_semantic_search(self) -> None:
        """测试语义搜索功能"""
        logger.info("🔍 开始测试语义搜索功能...")

        test_queries = [
            "Python编程",
            "向量数据库",
            "深度学习技术",
            "NoSQL数据库",
            "内存缓存",
            "并发编程",
        ]

        for test_query in test_queries:
            docs, scores = _test_search(test_query, top_k=3)

            assert isinstance(docs, list), f"搜索结果应该是列表: {test_query}"
            assert isinstance(scores, list), f"相似度分数应该是列表: {test_query}"
            assert len(docs) == len(scores), f"文档和分数数量应该一致: {test_query}"
            assert len(docs) <= 3, f"返回结果不应超过top_k: {test_query}"

            logger.info(f"🔍 测试查询: '{test_query}' - 找到 {len(docs)} 个结果")

            for i, (doc, score) in enumerate(zip(docs, scores)):
                assert isinstance(doc, str), f"文档内容应该是字符串: {test_query}"
                assert isinstance(
                    score, (int, float)
                ), f"相似度分数应该是数字: {test_query}"
                assert 0 <= score <= 1, f"相似度分数应该在0-1之间: {score}"
                logger.info(f"  [{i+1}] 相似度: {score:.3f}, 内容: {doc[:50]}...")

        logger.success("✅ 语义搜索功能测试通过！")

    def test_similarity_score_improvement(self) -> None:
        """测试相似度计算算法的准确性"""
        logger.info("🎯 开始测试相似度分数准确性...")

        high_relevance_queries = [
            "Python",
            "PostgreSQL",
            "机器学习",
        ]

        logger.info("📊 测试高相关度查询...")
        for query in high_relevance_queries:
            docs, scores = _test_search(query, top_k=3)

            if len(scores) > 0:
                best_score = max(scores)
                logger.info(f"🔍 查询: '{query}' - 最高相似度: {best_score:.3f}")
                assert best_score > 0.3, f"高相关查询的最高相似度过低: {query}"

        logger.success("✅ 相似度分数准确性测试通过！")

    def test_collection_isolation(self) -> None:
        """测试 collection 之间的隔离"""
        logger.info("🔒 开始测试 collection 隔离...")

        docs, scores = search_documents(
            "Python", "test_rag_collection_does_not_exist", embedding_model, top_k=5
        )
        assert docs == [], "不存在的 collection 应返回空结果"
        assert scores == [], "不存在的 collection 应返回空分数列表"

        logger.success("✅ collection 隔离测试通过！")

    def test_error_handling(self) -> None:
        """测试错误处理：空查询、无效 top_k"""
        logger.info("⚠️ 开始测试错误处理...")

        docs, scores = _test_search("", top_k=3)
        assert isinstance(docs, list) and isinstance(scores, list)

        docs, scores = _test_search("Python", top_k=0)
        assert docs == [] and scores == []

        logger.success("✅ 错误处理测试通过！")
