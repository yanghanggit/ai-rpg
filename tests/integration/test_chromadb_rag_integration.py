#!/usr/bin/env python3
"""
ChromaDB RAG系统集成测试

用于验证改造后的RAG系统是否能正常初始化和运行
"""

from typing import Generator, cast
import pytest
import asyncio
import time
from loguru import logger

from src.ai_rpg.chroma import (
    get_chroma_db,
    chromadb_clear_database,
)
from src.ai_rpg.rag import (
    load_knowledge_base_to_vector_db,
    search_similar_documents,  # 导入重构后的函数
)
from src.ai_rpg.embedding_model.sentence_transformer_embedding_model import (
    get_embedding_model,
)
from src.ai_rpg.demo.campaign_setting import (
    FANTASY_WORLD_RPG_KNOWLEDGE_BASE,
)


def _init_rag_system_with_model() -> bool:
    """辅助函数：使用默认模型初始化RAG系统"""
    embedding_model = get_embedding_model()
    if embedding_model is None:
        return False
    chroma_db = get_chroma_db()
    return load_knowledge_base_to_vector_db(
        FANTASY_WORLD_RPG_KNOWLEDGE_BASE, embedding_model, chroma_db
    )


def _rag_search_with_defaults(
    query: str, top_k: int = 5
) -> tuple[list[str], list[float]]:
    """辅助函数：使用默认实例执行语义搜索"""
    chroma_db = get_chroma_db()
    embedding_model = get_embedding_model()
    if embedding_model is None:
        return [], []
    return search_similar_documents(query, chroma_db, embedding_model, top_k)


class TestChromaDBRAGIntegration:
    """ChromaDB RAG系统集成测试类"""

    _db_initialized = False  # 类级别的标志，确保只初始化一次

    def test_chromadb_initialization(self) -> None:
        """测试ChromaDB初始化"""
        logger.info("🧪 开始测试ChromaDB RAG系统初始化...")

        # 测试ChromaDB实例创建
        chroma_db = get_chroma_db()
        assert chroma_db is not None, "ChromaDB实例创建失败"
        logger.info(f"✅ ChromaDB实例创建成功: {type(chroma_db)}")

        # 获取嵌入模型
        embedding_model = get_embedding_model()
        assert embedding_model is not None, "嵌入模型初始化失败"

        # 测试完整初始化
        success = load_knowledge_base_to_vector_db(
            FANTASY_WORLD_RPG_KNOWLEDGE_BASE, embedding_model, chroma_db
        )
        assert success, "ChromaDB RAG系统初始化失败"
        logger.success("🎉 ChromaDB RAG系统初始化测试通过！")

    def test_semantic_search(self) -> None:
        """测试语义搜索功能"""
        logger.info("🔍 开始测试语义搜索功能...")

        # 确保系统已初始化
        chroma_db = get_chroma_db()
        if not chroma_db.initialized:
            success = _init_rag_system_with_model()
            assert success, "系统初始化失败"

        # 确保数据库中有数据
        assert chroma_db.collection is not None, "ChromaDB集合应该已创建"
        collection_count = chroma_db.collection.count()
        if collection_count == 0:
            success = _init_rag_system_with_model()
            assert success, "系统初始化失败"
            collection_count = chroma_db.collection.count()
            assert collection_count > 0, f"初始化后数据库仍为空"

        # 测试语义搜索
        test_queries = [
            "晨曦之刃的神圣技能",
            "艾尔法尼亚大陆有哪些王国",
            "魔王阿巴顿的弱点",
            "冒险者公会的等级制度",
            "时之沙漏的神秘力量",
            "精灵的魔法能力",
            "失落的贤者之塔",
            "暴风雪团的成员组成",
        ]

        for test_query in test_queries:
            docs, scores = _rag_search_with_defaults(test_query, top_k=3)

            # 验证搜索结果
            assert isinstance(docs, list), f"搜索结果应该是列表: {test_query}"
            assert isinstance(scores, list), f"相似度分数应该是列表: {test_query}"
            assert len(docs) == len(scores), f"文档和分数数量应该一致: {test_query}"

            logger.info(f"🔍 测试查询: '{test_query}' - 找到 {len(docs)} 个结果")

            for i, (doc, score) in enumerate(zip(docs, scores)):
                assert isinstance(doc, str), f"文档内容应该是字符串: {test_query}"
                assert isinstance(
                    score, (int, float)
                ), f"相似度分数应该是数字: {test_query}"
                assert 0 <= score <= 1, f"相似度分数应该在0-1之间: {score}"
                logger.info(f"  [{i+1}] 相似度: {score:.3f}, 内容: {doc[:50]}...")

    def test_database_state(self) -> None:
        """测试数据库状态"""
        logger.info("📊 开始测试数据库状态...")

        chroma_db = get_chroma_db()

        # 确保系统已初始化
        if not chroma_db.initialized:
            success = _init_rag_system_with_model()
            assert success, "系统初始化失败"

        # 验证数据库状态
        assert chroma_db.initialized, "数据库应该已初始化"
        assert chroma_db.client is not None, "ChromaDB客户端应该已创建"
        assert chroma_db.collection is not None, "ChromaDB集合应该已创建"

        # 验证全局嵌入模型已加载
        embedding_model = get_embedding_model()
        assert embedding_model is not None, "嵌入模型应该已加载"

        # 验证集合中有数据
        collection_count = chroma_db.collection.count()
        assert collection_count > 0, f"集合中应该有数据，当前数量: {collection_count}"
        logger.info(f"📊 数据库状态正常，文档数量: {collection_count}")

    def test_error_handling(self) -> None:
        """测试错误处理"""
        logger.info("⚠️ 开始测试错误处理...")

        chroma_db = get_chroma_db()

        # 确保系统已初始化
        if not chroma_db.initialized:
            success = _init_rag_system_with_model()
            assert success, "系统初始化失败"

        # 测试空查询
        docs, scores = _rag_search_with_defaults("", top_k=3)
        assert isinstance(docs, list), "空查询应该返回列表"
        assert isinstance(scores, list), "空查询应该返回分数列表"

        # 测试异常查询参数
        docs, scores = _rag_search_with_defaults("测试查询", top_k=0)
        assert isinstance(docs, list), "异常参数应该返回列表"
        assert isinstance(scores, list), "异常参数应该返回分数列表"

        logger.info("⚠️ 错误处理测试通过")

    async def test_parallel_semantic_search(self) -> None:
        """测试并行语义搜索功能"""
        logger.info("🚀 开始测试并行语义搜索功能...")

        # 确保系统已初始化
        chroma_db = get_chroma_db()
        if not chroma_db.initialized:
            success = _init_rag_system_with_model()
            assert success, "系统初始化失败"

        # 确保数据库中有数据
        assert chroma_db.collection is not None, "ChromaDB集合应该已创建"
        collection_count = chroma_db.collection.count()
        if collection_count == 0:
            success = _init_rag_system_with_model()
            assert success, "系统初始化失败"
            collection_count = chroma_db.collection.count()
            assert collection_count > 0, f"初始化后数据库仍为空"

        # 定义多个测试查询
        test_queries = [
            "晨曦之刃的神圣技能",
            "艾尔法尼亚大陆有哪些王国",
            "魔王阿巴顿的弱点",
            "冒险者公会的等级制度",
            "时之沙漏的神秘力量",
            "精灵的魔法能力",
            "失落的贤者之塔",
            "暴风雪团的成员组成",
        ]

        # 创建异步任务包装器
        async def async_search(query: str) -> tuple[str, list[str], list[float]]:
            """异步搜索包装器 - 使用推荐的 asyncio.to_thread 方法"""
            chroma_db = get_chroma_db()
            embedding_model = get_embedding_model()
            if embedding_model is None:
                return query, [], []
            docs, scores = await asyncio.to_thread(
                search_similar_documents, query, chroma_db, embedding_model, 3
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
                # 使用类型断言确保mypy理解这里的类型
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

            for i, (doc, score) in enumerate(zip(docs, scores)):
                assert isinstance(doc, str), f"文档内容应该是字符串: {query}"
                assert isinstance(score, (int, float)), f"相似度分数应该是数字: {query}"
                assert 0 <= score <= 1, f"相似度分数应该在0-1之间: {score}"

        # 比较串行执行时间（可选）
        logger.info("⏱️ 开始串行执行对比测试...")
        start_time = time.time()

        for query in test_queries:
            docs, scores = _rag_search_with_defaults(query, top_k=3)
            assert isinstance(docs, list) and isinstance(scores, list)

        serial_time = time.time() - start_time
        logger.info(f"⏱️ 串行搜索耗时: {serial_time:.2f}秒")

        # 计算性能提升
        if serial_time > 0:
            speedup = serial_time / parallel_time
            logger.success(f"🚀 并行搜索性能提升: {speedup:.2f}x")

        logger.success("🎉 并行语义搜索测试通过！")

    def test_parallel_semantic_search_sync(self) -> None:
        """同步调用并行语义搜索测试的包装器"""
        logger.info("🔄 启动并行语义搜索测试...")
        asyncio.run(self.test_parallel_semantic_search())

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self) -> Generator[None, None, None]:
        """测试前后的设置和清理"""
        logger.info("🔧 测试环境设置...")

        # 只在第一次测试时清理数据库，确保使用干净的测试环境
        if not TestChromaDBRAGIntegration._db_initialized:
            chromadb_clear_database()
            logger.info("🧹 首次测试前：清理了现有数据库，准备创建新的测试数据")
            TestChromaDBRAGIntegration._db_initialized = True
        else:
            logger.info("🔄 后续测试：复用现有数据库环境")

        yield

        # 测试结束后保留数据库，不再清理
        logger.info("🧹 测试结束：保留数据库数据供后续使用")
        logger.info("🧹 测试环境清理完成")


# 独立运行时的入口
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
