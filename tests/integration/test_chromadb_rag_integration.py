#!/usr/bin/env python3
"""
ChromaDB RAG系统集成测试

用于验证改造后的RAG系统是否能正常初始化和运行
"""

from typing import Generator
import pytest
from loguru import logger

from src.multi_agents_game.chroma import (
    get_chroma_db,
    chromadb_clear_database,
)
from src.multi_agents_game.rag import (
    initialize_rag_system,
    rag_semantic_search,  # 添加全局语义搜索函数
)
from src.multi_agents_game.embedding_model.sentence_transformer_embedding_model import (
    get_embedding_model,
)
from src.multi_agents_game.demo.campaign_setting import (
    FANTASY_WORLD_RPG_KNOWLEDGE_BASE,
)


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

        # 测试完整初始化
        success = initialize_rag_system(FANTASY_WORLD_RPG_KNOWLEDGE_BASE)
        assert success, "ChromaDB RAG系统初始化失败"
        logger.success("🎉 ChromaDB RAG系统初始化测试通过！")

    def test_semantic_search(self) -> None:
        """测试语义搜索功能"""
        logger.info("🔍 开始测试语义搜索功能...")

        # 确保系统已初始化
        chroma_db = get_chroma_db()
        if not chroma_db.initialized:
            success = initialize_rag_system(FANTASY_WORLD_RPG_KNOWLEDGE_BASE)
            assert success, "系统初始化失败"

        # 确保数据库中有数据
        assert chroma_db.collection is not None, "ChromaDB集合应该已创建"
        collection_count = chroma_db.collection.count()
        if collection_count == 0:
            success = initialize_rag_system(FANTASY_WORLD_RPG_KNOWLEDGE_BASE)
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
            docs, scores = rag_semantic_search(test_query, top_k=3)

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
            success = initialize_rag_system(FANTASY_WORLD_RPG_KNOWLEDGE_BASE)
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
            success = initialize_rag_system(FANTASY_WORLD_RPG_KNOWLEDGE_BASE)
            assert success, "系统初始化失败"

        # 测试空查询
        docs, scores = rag_semantic_search("", top_k=3)
        assert isinstance(docs, list), "空查询应该返回列表"
        assert isinstance(scores, list), "空查询应该返回分数列表"

        # 测试异常查询参数
        docs, scores = rag_semantic_search("测试查询", top_k=0)
        assert isinstance(docs, list), "异常参数应该返回列表"
        assert isinstance(scores, list), "异常参数应该返回分数列表"

        logger.info("⚠️ 错误处理测试通过")

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
