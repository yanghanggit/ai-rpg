#!/usr/bin/env python3
"""
ChromaDB RAG系统集成测试

用于验证改造后的RAG系统是否能正常初始化和运行

测试策略：
1. 创建独立的测试知识库（与主系统隔离）
2. 使用独立的 ChromaDB collection（不影响主系统）
3. 测试所有核心 RAG 功能
"""

from typing import Dict, List, Generator, cast
import pytest
import asyncio
import time
from loguru import logger
from chromadb.api.models.Collection import Collection

from src.ai_rpg.chroma import chroma_client
from src.ai_rpg.rag import add_documents, search_documents
from src.ai_rpg.embedding_model import multilingual_model


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
        "ChromaDB是一个向量数据库，专门用于存储和检索嵌入向量",
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
def _get_test_collection() -> Collection:
    """获取或创建测试专用的 collection"""
    return chroma_client.get_or_create_collection(
        name=TEST_COLLECTION_NAME,
        metadata={
            "description": "RAG集成测试专用集合",
            "hnsw:space": "cosine",
        },
    )


def _init_test_rag_system() -> bool:
    """初始化测试专用的 RAG 系统"""
    collection = _get_test_collection()

    # 检查是否已经初始化
    if collection.count() > 0:
        logger.info(f"测试collection已有数据，跳过初始化")
        return True

    # 准备文档数据：将 Dict[str, List[str]] 展开为 flat lists
    documents_list: List[str] = []
    metadatas_list: List[Dict[str, str]] = []
    ids_list: List[str] = []

    doc_index = 0
    for category, docs in TEST_KNOWLEDGE_BASE.items():
        for doc in docs:
            documents_list.append(doc)
            metadatas_list.append({"category": category})
            ids_list.append(f"test_{category}_{doc_index}")
            doc_index += 1

    # 调用 add_documents
    logger.info(f"开始加载测试知识库，共 {len(documents_list)} 个文档")
    return add_documents(
        collection=collection,
        embedding_model=multilingual_model,
        documents=documents_list,
        metadatas=metadatas_list,
        ids=ids_list,
    )


def _test_search(query: str, top_k: int = 5) -> tuple[list[str], list[float]]:
    """测试专用的语义搜索函数"""
    collection = _get_test_collection()
    return search_documents(query, collection, multilingual_model, top_k)


class TestChromaDBRAGIntegration:
    """ChromaDB RAG系统集成测试类"""

    _test_collection_initialized = False  # 类级别标志，确保只初始化一次

    def test_chromadb_initialization(self) -> None:
        """测试ChromaDB初始化"""
        logger.info("🧪 开始测试ChromaDB RAG系统初始化...")

        # 测试 ChromaDB collection 创建
        collection = _get_test_collection()
        assert collection is not None, "ChromaDB collection创建失败"
        logger.info(f"✅ ChromaDB collection创建成功: {type(collection)}")

        # 获取嵌入模型
        assert multilingual_model is not None, "预加载的多语言模型不可用"

        # 测试完整初始化
        success = _init_test_rag_system()
        assert success, "ChromaDB RAG系统初始化失败"

        # 验证数据已加载
        doc_count = collection.count()
        expected_count = sum(len(docs) for docs in TEST_KNOWLEDGE_BASE.values())
        assert (
            doc_count == expected_count
        ), f"文档数量不符: 期望{expected_count}, 实际{doc_count}"

        logger.success(f"🎉 ChromaDB RAG系统初始化测试通过！文档数量: {doc_count}")

    def test_semantic_search(self) -> None:
        """测试语义搜索功能"""
        logger.info("🔍 开始测试语义搜索功能...")

        # 确保测试数据已加载
        collection = _get_test_collection()
        if collection.count() == 0:
            success = _init_test_rag_system()
            assert success, "系统初始化失败"

        # 测试语义搜索
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

            # 验证搜索结果
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

        # 确保测试数据已加载
        collection = _get_test_collection()
        if collection.count() == 0:
            success = _init_test_rag_system()
            assert success, "系统初始化失败"

        # 测试高相关度查询（应该得到较高的相似度分数）
        high_relevance_queries = [
            "Python",  # 直接匹配知识库中的内容
            "PostgreSQL",  # 精确匹配
            "机器学习",  # 核心概念
        ]

        logger.info("📊 测试高相关度查询...")
        for query in high_relevance_queries:
            docs, scores = _test_search(query, top_k=3)

            if len(scores) > 0:
                best_score = max(scores)
                logger.info(f"🔍 查询: '{query}' - 最高相似度: {best_score:.3f}")

                # 高相关查询应该得到较高的相似度分数（>0.3）
                assert (
                    best_score > 0.3
                ), f"高相关查询 '{query}' 的最高相似度过低: {best_score:.3f}"

                # 打印详细结果
                for i, (doc, score) in enumerate(zip(docs[:3], scores[:3])):
                    logger.info(f"  [{i+1}] 相似度: {score:.3f}, 内容: {doc[:60]}...")

        # 测试中等相关度查询
        medium_relevance_queries = [
            "编程工具",  # 相关但不精确匹配
            "数据存储",  # 主题相关
        ]

        logger.info("📊 测试中等相关度查询...")
        for query in medium_relevance_queries:
            docs, scores = _test_search(query, top_k=3)

            if len(scores) > 0:
                best_score = max(scores)
                logger.info(f"🔍 查询: '{query}' - 最高相似度: {best_score:.3f}")

                # 中等相关查询应该有合理的分数
                assert (
                    best_score > 0.1
                ), f"中等相关查询 '{query}' 的相似度分数过低: {best_score:.3f}"

        # 测试相似度分数的区分度
        logger.info("📊 测试相似度分数的区分度...")
        high_query = "Python"
        medium_query = "编程工具"

        docs_high, scores_high = _test_search(high_query, top_k=1)
        docs_medium, scores_medium = _test_search(medium_query, top_k=1)

        if len(scores_high) > 0 and len(scores_medium) > 0:
            logger.info(f"🔍 高相关查询 '{high_query}': {scores_high[0]:.3f}")
            logger.info(f"🔍 中等相关查询 '{medium_query}': {scores_medium[0]:.3f}")

            # 高相关查询的分数应该不低于中等相关查询
            assert (
                scores_high[0] >= scores_medium[0] * 0.8
            ), f"相似度分数排序不合理: 高相关({scores_high[0]:.3f}) < 中等相关({scores_medium[0]:.3f})"

        logger.success("✅ 相似度分数准确性测试通过！")

    def test_database_state(self) -> None:
        """测试数据库状态"""
        logger.info("📊 开始测试数据库状态...")

        # 获取测试collection
        collection = _get_test_collection()
        assert collection is not None, "ChromaDB集合应该已创建"
        assert chroma_client is not None, "ChromaDB客户端应该已创建"

        # 确保数据库中有数据
        collection_count = collection.count()
        if collection_count == 0:
            success = _init_test_rag_system()
            assert success, "系统初始化失败"
            collection_count = collection.count()

        # 验证全局嵌入模型已加载
        assert multilingual_model is not None, "预加载的多语言模型不可用"

        # 验证集合中有数据
        expected_count = sum(len(docs) for docs in TEST_KNOWLEDGE_BASE.values())
        assert (
            collection_count == expected_count
        ), f"集合中文档数量不符: 期望{expected_count}, 实际{collection_count}"
        logger.info(f"📊 数据库状态正常，文档数量: {collection_count}")
        logger.success("✅ 数据库状态测试通过！")

    def test_error_handling(self) -> None:
        """测试错误处理"""
        logger.info("⚠️ 开始测试错误处理...")

        # 确保数据库中有数据
        collection = _get_test_collection()
        if collection.count() == 0:
            success = _init_test_rag_system()
            assert success, "系统初始化失败"

        # 测试空查询
        docs, scores = _test_search("", top_k=3)
        assert isinstance(docs, list), "空查询应该返回列表"
        assert isinstance(scores, list), "空查询应该返回分数列表"
        logger.info(f"空查询返回: {len(docs)} 个结果")

        # 测试异常查询参数
        docs, scores = _test_search("测试查询", top_k=0)
        assert isinstance(docs, list), "异常参数应该返回列表"
        assert isinstance(scores, list), "异常参数应该返回分数列表"
        logger.info(f"top_k=0查询返回: {len(docs)} 个结果")

        logger.success("✅ 错误处理测试通过！")

    async def test_parallel_semantic_search(self) -> None:
        """测试并行语义搜索功能"""
        logger.info("🚀 开始测试并行语义搜索功能...")

        # 确保测试数据已加载
        collection = _get_test_collection()
        if collection.count() == 0:
            success = _init_test_rag_system()
            assert success, "系统初始化失败"

        # 定义多个测试查询
        test_queries = [
            "Python编程",
            "数据库系统",
            "机器学习",
            "向量数据库",
            "并发编程",
            "自然语言处理",
        ]

        # 创建异步任务包装器
        async def async_search(query: str) -> tuple[str, list[str], list[float]]:
            """异步搜索包装器"""
            docs, scores = await asyncio.to_thread(
                _test_search,
                query,
                3,
            )
            return query, docs, scores

        # 记录开始时间
        start_time = time.time()

        # 并行执行所有搜索查询
        logger.info(f"🔍 并行执行 {len(test_queries)} 个搜索查询...")
        results = await asyncio.gather(
            *[async_search(query) for query in test_queries], return_exceptions=True
        )

        # 记录结束时间
        parallel_time = time.time() - start_time
        logger.info(f"⚡ 并行搜索耗时: {parallel_time:.2f}秒")

        # 验证并行搜索结果
        successful_results: list[tuple[str, list[str], list[float]]] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"搜索失败: {result}")
                pytest.fail(f"并行搜索中出现异常: {result}")
            else:
                successful_results.append(
                    cast(tuple[str, list[str], list[float]], result)
                )

        assert len(successful_results) == len(test_queries), "所有查询都应该成功"

        # 验证每个搜索结果
        for query, docs, scores in successful_results:
            assert isinstance(docs, list), f"搜索结果应该是列表: {query}"
            assert isinstance(scores, list), f"相似度分数应该是列表: {query}"
            assert len(docs) == len(scores), f"文档和分数数量应该一致: {query}"

            logger.info(f"🔍 并行查询: '{query}' - 找到 {len(docs)} 个结果")

            for doc, score in zip(docs, scores):
                assert isinstance(doc, str), f"文档内容应该是字符串: {query}"
                assert isinstance(score, (int, float)), f"相似度分数应该是数字: {query}"
                assert 0 <= score <= 1, f"相似度分数应该在0-1之间: {score}"

        # 比较串行执行时间（可选）
        logger.info("⏱️ 开始串行执行对比测试...")
        start_time = time.time()

        for query in test_queries:
            docs, scores = _test_search(query, top_k=3)
            assert isinstance(docs, list) and isinstance(scores, list)

        serial_time = time.time() - start_time
        logger.info(f"⏱️ 串行搜索耗时: {serial_time:.2f}秒")

        # 计算性能提升
        if serial_time > 0 and parallel_time > 0:
            speedup = serial_time / parallel_time
            logger.success(f"🚀 并行搜索性能提升: {speedup:.2f}x")

        logger.success("✅ 并行语义搜索测试通过！")

    def test_parallel_semantic_search_sync(self) -> None:
        """同步调用并行语义搜索测试的包装器"""
        logger.info("🔄 启动并行语义搜索测试...")
        asyncio.run(self.test_parallel_semantic_search())

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self) -> Generator[None, None, None]:
        """测试前后的设置和清理"""
        logger.info("🔧 测试环境设置...")

        # 只在第一次测试时初始化数据
        if not TestChromaDBRAGIntegration._test_collection_initialized:
            logger.info("🚀 首次测试：初始化测试专用collection...")
            success = _init_test_rag_system()
            if success:
                TestChromaDBRAGIntegration._test_collection_initialized = True
                logger.success("✅ 测试数据初始化完成")
            else:
                logger.error("❌ 测试数据初始化失败")
        else:
            logger.info("🔄 后续测试：复用现有测试数据")

        yield

        # 测试结束后保留测试数据
        logger.info("🧹 测试结束：保留测试数据供后续使用")


# ============================================================================
# 清理函数（可手动调用）
# ============================================================================
def cleanup_test_collection() -> None:
    """清理测试专用的 collection（可选，手动调用）"""
    try:
        chroma_client.delete_collection(name=TEST_COLLECTION_NAME)
        logger.info(f"🗑️ 已删除测试collection: {TEST_COLLECTION_NAME}")
    except Exception as e:
        logger.warning(f"⚠️ 删除测试collection失败（可能不存在）: {e}")


# 独立运行时的入口
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
