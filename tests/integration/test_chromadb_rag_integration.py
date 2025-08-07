#!/usr/bin/env python3
"""
ChromaDB RAG系统集成测试

用于验证改造后的RAG系统是否能正常初始化和运行
"""

from typing import Generator, Dict, List, Final
import pytest
from loguru import logger

from src.multi_agents_game.db.chromadb_client import (
    get_chroma_db,
    chromadb_clear_database,
)
from src.multi_agents_game.db.rag_ops import (
    initialize_rag_system,
    rag_semantic_search,  # 添加全局语义搜索函数
)
from src.multi_agents_game.db.embedding_manager import get_embedding_model

# 测试用模拟知识库数据
TEST_RPG_KNOWLEDGE_BASE: Final[Dict[str, List[str]]] = {
    "测试世界": [
        "测试世界是一个神奇的幻想大陆，有三个主要王国：光明王国、暗影王国和中立王国。",
        "这个世界充满了魔法和奇幻生物，冒险者们在这里探索未知的秘密。",
        "古老的传说说这个世界曾经被一位强大的法师创造，用于测试勇敢的冒险者。",
    ],
    "测试圣剑": [
        "测试圣剑名为「真理之刃」，是一把拥有神秘力量的武器。",
        "只有通过智慧和勇气试炼的人才能挥舞这把剑。",
        "剑身上刻着古老的符文，能够发出纯净的光芒驱散黑暗。",
        "传说中，这把剑能够揭示真相，让谎言无所遁形。",
    ],
    "测试魔王": [
        "测试魔王是一个强大的邪恶存在，名为「虚假之主」。",
        "他的力量来源于谎言和欺骗，能够迷惑人心。",
        "击败他的唯一方法是用真理之刃破除他的幻象。",
        "据说他被封印在世界的最深处，但封印正在逐渐减弱。",
    ],
    "测试种族": [
        "光明族是善良的种族，擅长治疗魔法和防护法术。",
        "暗影族虽然看起来神秘，但并非邪恶，他们是出色的刺客和侦察者。",
        "中立族是平衡的守护者，拥有调和各种力量的能力。",
        "还有传说中的智慧族，他们隐居在高山之巅，掌握着古老的知识。",
    ],
    "测试遗迹": [
        "真理神殿：供奉真理之神的圣地，内有古老的智慧石碑。",
        "迷雾森林：充满幻象的森林，只有心智坚定的人才能穿越。",
        "知识宝库：古代学者建立的图书馆，藏有无数珍贵的魔法书籍。",
        "试炼之塔：测试冒险者能力的高塔，每一层都有不同的挑战。",
    ],
    "测试冒险者": [
        "测试世界的冒险者公会欢迎所有勇敢的探索者。",
        "公会提供各种任务，从简单的采集到困难的怪物讨伐。",
        "著名的冒险者团队「真理探求者」由各个种族的精英组成。",
        "冒险者的基本装备包括魔法水晶、治疗药水和传送法阵。",
    ],
    "测试秘宝": [
        "智慧之石：能够增强使用者理解力的神秘宝石。",
        "时间齿轮：据说能够短暂操控时间流速的奇妙装置。",
        "生命之花：传说中能够复活死者的神奇植物。",
        "这些宝物隐藏在世界各地，等待有缘人的发现。",
    ],
}


class TestChromaDBRAGIntegration:
    """ChromaDB RAG系统集成测试类"""

    def test_chromadb_initialization(self) -> None:
        """测试ChromaDB初始化"""
        logger.info("🧪 开始测试ChromaDB RAG系统初始化...")

        # 测试ChromaDB实例创建
        chroma_db = get_chroma_db()
        assert chroma_db is not None, "ChromaDB实例创建失败"
        logger.info(f"✅ ChromaDB实例创建成功: {type(chroma_db)}")

        # 测试完整初始化
        success = initialize_rag_system(TEST_RPG_KNOWLEDGE_BASE)
        assert success, "ChromaDB RAG系统初始化失败"
        logger.success("🎉 ChromaDB RAG系统初始化测试通过！")

    def test_semantic_search(self) -> None:
        """测试语义搜索功能"""
        logger.info("🔍 开始测试语义搜索功能...")

        # 确保系统已初始化
        chroma_db = get_chroma_db()
        if not chroma_db.initialized:
            success = initialize_rag_system(TEST_RPG_KNOWLEDGE_BASE)
            assert success, "系统初始化失败"

        # 确保数据库中有数据
        assert chroma_db.collection is not None, "ChromaDB集合应该已创建"
        collection_count = chroma_db.collection.count()
        if collection_count == 0:
            success = initialize_rag_system(TEST_RPG_KNOWLEDGE_BASE)
            assert success, "系统初始化失败"
            collection_count = chroma_db.collection.count()
            assert collection_count > 0, f"初始化后数据库仍为空"

        # 测试语义搜索
        test_queries = [
            "真理之刃的能力",
            "测试世界有哪些王国",
            "虚假之主的弱点",
            "冒险者公会",
            "智慧之石的作用",
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
            success = initialize_rag_system(TEST_RPG_KNOWLEDGE_BASE)
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
            success = initialize_rag_system(TEST_RPG_KNOWLEDGE_BASE)
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
        
        # 测试开始前清理数据库以确保使用测试数据
        chromadb_clear_database()
        logger.info("🧹 测试开始前：清理了现有数据库")
        
        yield
        
        # 测试结束后再次清理数据库，确保不影响其他模块
        chromadb_clear_database()
        logger.info("🧹 测试结束后：清理了数据库，确保不影响其他模块")
        logger.info("🧹 测试环境清理完成")


# 独立运行时的入口
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
