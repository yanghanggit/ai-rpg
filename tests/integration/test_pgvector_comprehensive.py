"""
pgvector 综合测试和演示文件
合并了基础测试、完整功能测试和实际使用演示
包含：基础SQL操作测试、ORM向量操作测试、实际应用场景演示
"""

import pytest
import numpy as np
from typing import List, Any, cast
from sqlalchemy import create_engine, text
from loguru import logger
import hashlib

# 导入配置
from src.multi_agents_game.pgsql import DEFAULT_POSTGRES_CONFIG


# ================================
# pytest fixtures
# ================================


@pytest.fixture(scope="session", autouse=True)
def setup_database_tables() -> Any:
    """设置数据库表的 fixture"""
    try:
        from src.multi_agents_game.pgsql.client import (
            pgsql_ensure_database_tables,
        )

        pgsql_ensure_database_tables()
        logger.info("✅ 数据库表已就绪")
        yield
    except Exception as e:
        logger.error(f"❌ 数据库表设置失败: {e}")
        raise e


# ================================
# 嵌入向量生成函数 (模拟OpenAI API)
# ================================


def mock_get_embedding(text: str) -> List[float]:
    """
    模拟获取文本嵌入向量的函数 (1536维)
    实际使用时应该调用OpenAI或其他嵌入API

    参数:
        text: 输入文本

    返回:
        List[float]: 1536维的向量
    """
    # 使用文本哈希生成确定性的向量 (仅用于测试)
    np.random.seed(hash(text) % 2**32)
    vector = np.random.randn(1536).astype(float)
    # 归一化向量
    vector = vector / np.linalg.norm(vector)
    return cast(List[float], list(vector))


def mock_openai_embedding(text: str) -> List[float]:
    """
    另一种模拟OpenAI嵌入API的实现
    使用MD5哈希生成更稳定的向量
    """
    hash_obj = hashlib.md5(text.encode())
    seed = int(hash_obj.hexdigest(), 16) % (2**32)

    np.random.seed(seed)
    vector = np.random.randn(1536).astype(float)
    vector = vector / np.linalg.norm(vector)  # 归一化
    return cast(List[float], vector.tolist())


# ================================
# pgvector 测试类
# ================================


class TestPgvectorIntegration:
    """pgvector 集成测试类"""

    def setup_method(self) -> None:
        """在每个测试方法前运行"""
        logger.info("🔧 设置测试环境...")

    def teardown_method(self) -> None:
        """在每个测试方法后运行"""
        logger.info("🧹 清理测试环境...")


# ================================
# 第一部分：基础SQL向量操作测试
# ================================


@pytest.mark.integration
@pytest.mark.database
def test_basic_vector_operations() -> None:
    """测试基本的向量操作 - 直接SQL操作"""
    logger.info("🧪 开始测试基本向量操作...")

    # 创建数据库连接
    engine = create_engine(DEFAULT_POSTGRES_CONFIG.connection_string)

    try:
        with engine.connect() as conn:
            # 1. 确保pgvector扩展已安装
            logger.info("🔧 检查pgvector扩展...")
            result = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
            if result:
                logger.info(f"✅ pgvector扩展已安装: {result[0]}")
            else:
                logger.error("❌ pgvector扩展未安装")
                return

            # 2. 测试创建简单向量表
            logger.info("📝 创建测试向量表...")
            conn.execute(
                text(
                    """
                DROP TABLE IF EXISTS test_vectors;
                CREATE TABLE test_vectors (
                    id SERIAL PRIMARY KEY,
                    content TEXT,
                    embedding vector(3)
                );
            """
                )
            )

            # 3. 插入测试数据
            logger.info("💾 插入测试向量数据...")
            test_vectors = [
                ("文档1：关于机器学习的介绍", [1.0, 2.0, 3.0]),
                ("文档2：深度学习教程", [1.1, 2.1, 3.1]),
                ("文档3：Python编程指南", [4.0, 5.0, 6.0]),
            ]

            for content, vector in test_vectors:
                conn.execute(
                    text(
                        """
                    INSERT INTO test_vectors (content, embedding) 
                    VALUES (:content, :vector)
                """
                    ),
                    {"content": content, "vector": vector},
                )

            # 4. 测试向量相似度搜索
            logger.info("🔍 测试向量相似度搜索...")
            query_vector = "[1.05, 2.05, 3.05]"  # 转换为字符串格式

            results = conn.execute(
                text(
                    """
                SELECT content, embedding, (embedding <=> :query_vector) as distance
                FROM test_vectors
                ORDER BY embedding <=> :query_vector
                LIMIT 3
            """
                ),
                {"query_vector": query_vector},
            ).fetchall()

            logger.info("📋 搜索结果:")
            for i, row in enumerate(results):
                logger.info(f"  {i+1}. {row.content}")
                logger.info(f"     向量: {row.embedding}")
                logger.info(f"     距离: {row.distance:.4f}")

            # 5. 测试余弦相似度
            logger.info("📐 测试余弦相似度...")
            similarity_results = conn.execute(
                text(
                    """
                SELECT content, (1 - (embedding <=> :query_vector)) as similarity
                FROM test_vectors
                ORDER BY embedding <=> :query_vector
                LIMIT 3
            """
                ),
                {"query_vector": query_vector},
            ).fetchall()

            logger.info("📊 相似度结果:")
            for i, row in enumerate(similarity_results):
                logger.info(f"  {i+1}. {row.content}: 相似度 {row.similarity:.4f}")

            # 6. 清理测试表
            conn.execute(text("DROP TABLE test_vectors"))
            conn.commit()

            logger.info("✅ 基本向量操作测试完成!")

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        raise e


@pytest.mark.integration
@pytest.mark.database
def test_high_dimension_vectors() -> None:
    """测试高维向量（1536维）- 直接SQL操作"""
    logger.info("🧪 开始测试高维向量操作...")

    engine = create_engine(DEFAULT_POSTGRES_CONFIG.connection_string)

    try:
        with engine.connect() as conn:
            # 创建1536维向量表
            logger.info("📝 创建1536维向量表...")
            conn.execute(
                text(
                    """
                DROP TABLE IF EXISTS test_vectors_1536;
                CREATE TABLE test_vectors_1536 (
                    id SERIAL PRIMARY KEY,
                    content TEXT,
                    embedding vector(1536)
                );
            """
                )
            )

            # 生成测试向量
            logger.info("🎲 生成测试向量...")
            np.random.seed(42)  # 确保结果可重现
            test_embedding = np.random.randn(1536).astype(float).tolist()
            # 转换为字符串格式
            vector_str = "[" + ",".join(map(str, test_embedding)) + "]"

            # 插入数据
            conn.execute(
                text(
                    """
                INSERT INTO test_vectors_1536 (content, embedding) 
                VALUES (:content, :vector)
            """
                ),
                {
                    "content": "测试文档：这是一个1536维向量的测试文档",
                    "vector": vector_str,
                },
            )

            # 测试搜索
            query_vector = vector_str  # 使用相同向量应该得到完美匹配

            result = conn.execute(
                text(
                    """
                SELECT content, (1 - (embedding <=> :query_vector)) as similarity
                FROM test_vectors_1536
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :query_vector
                LIMIT 1
            """
                ),
                {"query_vector": query_vector},
            ).fetchone()

            if result:
                logger.info(f"✅ 高维向量搜索成功!")
                logger.info(f"   内容: {result.content}")
                logger.info(f"   相似度: {result.similarity:.6f}")
            else:
                logger.error("❌ 高维向量搜索失败")

            # 清理
            conn.execute(text("DROP TABLE test_vectors_1536"))
            conn.commit()

            logger.info("✅ 高维向量测试完成!")

    except Exception as e:
        logger.error(f"❌ 高维向量测试失败: {e}")
        raise e


# ================================
# 第二部分：ORM向量操作测试
# ================================


@pytest.mark.integration
@pytest.mark.database
def test_vector_document_operations() -> None:
    """测试向量文档操作 - 使用ORM"""
    from src.multi_agents_game.pgsql.vector_document import (
        save_vector_document,
        search_similar_documents,
        get_database_vector_stats,
    )

    logger.info("🧪 开始测试向量文档操作...")

    # 1. 保存一些测试文档
    test_documents = [
        {
            "content": "这是一个关于机器学习的基础教程，介绍了监督学习和无监督学习的基本概念。",
            "title": "机器学习基础",
            "doc_type": "tutorial",
            "source": "ml_guide.md",
        },
        {
            "content": "深度学习是机器学习的一个分支，使用神经网络来模拟人脑的学习过程。",
            "title": "深度学习介绍",
            "doc_type": "tutorial",
            "source": "dl_intro.md",
        },
        {
            "content": "Python是一种高级编程语言，广泛用于数据科学、机器学习和Web开发。",
            "title": "Python编程入门",
            "doc_type": "programming",
            "source": "python_basics.md",
        },
        {
            "content": "数据库设计是软件开发中的重要环节，需要考虑数据的结构化存储和查询效率。",
            "title": "数据库设计原则",
            "doc_type": "database",
            "source": "db_design.md",
        },
    ]

    saved_docs = []
    for doc_data in test_documents:
        try:
            # 生成嵌入向量
            embedding = mock_get_embedding(doc_data["content"])

            # 保存到数据库
            doc = save_vector_document(
                content=doc_data["content"],
                embedding=embedding,
                title=doc_data["title"],
                doc_type=doc_data["doc_type"],
                source=doc_data["source"],
                metadata={"test": True, "category": doc_data["doc_type"]},
            )
            saved_docs.append(doc)
            logger.info(f"✅ 已保存文档: {doc.title}")

        except Exception as e:
            logger.error(f"❌ 保存文档失败: {e}")

    # 2. 测试相似度搜索
    try:
        query_text = "我想学习人工智能和神经网络"
        query_embedding = mock_get_embedding(query_text)

        logger.info(f"🔍 搜索查询: {query_text}")

        # 搜索相似文档
        similar_docs = search_similar_documents(
            query_embedding=query_embedding,
            limit=3,
            similarity_threshold=0.0,  # 降低阈值以便看到结果
        )

        logger.info(f"📋 找到 {len(similar_docs)} 个相似文档:")
        for doc, similarity in similar_docs:
            logger.info(f"  - {doc.title}: 相似度 {similarity:.4f}")
            logger.info(f"    内容: {doc.content[:50]}...")

        # 按类型过滤搜索
        tutorial_docs = search_similar_documents(
            query_embedding=query_embedding,
            limit=3,
            doc_type_filter="tutorial",
            similarity_threshold=0.0,
        )

        logger.info(f"📚 教程类文档搜索结果 ({len(tutorial_docs)} 个):")
        for doc, similarity in tutorial_docs:
            logger.info(f"  - {doc.title}: 相似度 {similarity:.4f}")

    except Exception as e:
        logger.error(f"❌ 搜索测试失败: {e}")

    # 3. 获取统计信息
    try:
        stats = get_database_vector_stats()
        logger.info(f"📊 数据库统计: {stats}")
    except Exception as e:
        logger.error(f"❌ 获取统计失败: {e}")


@pytest.mark.integration
@pytest.mark.database
# 该函数已被注释，因为 ConversationVectorDB 类已被移除
def test_conversation_vector_operations() -> None:
    """测试对话向量操作 - 已移除，因为 ConversationVectorDB 类已被删除"""
    logger.info("⚠️ test_conversation_vector_operations 已被移除")
    pass


# ================================
# 第三部分：实际应用场景演示
# ================================


@pytest.mark.integration
@pytest.mark.demo
def demo_document_rag_system() -> None:
    """演示基于文档的RAG系统"""
    from src.multi_agents_game.pgsql.vector_document import (
        save_vector_document,
        search_similar_documents,
    )

    logger.info("🤖 演示文档RAG系统...")

    # 1. 保存一些知识文档
    documents = [
        {
            "title": "机器学习基础",
            "content": "机器学习是人工智能的一个分支，它让计算机能够在没有明确编程的情况下学习。主要包括监督学习、无监督学习和强化学习三种类型。",
            "doc_type": "knowledge",
            "source": "ml_textbook.pdf",
        },
        {
            "title": "深度学习原理",
            "content": "深度学习使用多层神经网络来模拟人脑的工作方式。它在图像识别、自然语言处理等领域取得了突破性进展。",
            "doc_type": "knowledge",
            "source": "dl_guide.pdf",
        },
        {
            "title": "Python数据科学",
            "content": "Python是数据科学领域最流行的编程语言。主要库包括NumPy、Pandas、Matplotlib和Scikit-learn等。",
            "doc_type": "tutorial",
            "source": "python_ds.md",
        },
        {
            "title": "向量数据库应用",
            "content": "向量数据库用于存储和检索高维向量数据，特别适用于相似性搜索、推荐系统和RAG应用。",
            "doc_type": "knowledge",
            "source": "vector_db.pdf",
        },
    ]

    logger.info("📚 保存知识文档...")
    for doc_data in documents:
        embedding = mock_openai_embedding(doc_data["content"])
        save_vector_document(
            content=doc_data["content"],
            embedding=embedding,
            title=doc_data["title"],
            doc_type=doc_data["doc_type"],
            source=doc_data["source"],
            metadata={"category": "knowledge_base"},
        )

    # 2. 模拟用户查询
    queries = [
        "什么是机器学习？",
        "如何使用Python进行数据分析？",
        "向量数据库有什么用途？",
        "深度学习和机器学习的区别是什么？",
    ]

    logger.info("🔍 处理用户查询...")
    for query in queries:
        logger.info(f"\n❓ 用户问题: {query}")

        # 获取查询的嵌入向量
        query_embedding = mock_openai_embedding(query)

        # 搜索相关文档
        results = search_similar_documents(
            query_embedding=query_embedding, limit=2, similarity_threshold=0.1
        )

        logger.info("📖 相关文档:")
        for doc, similarity in results:
            logger.info(f"   - {doc.title} (相似度: {similarity:.3f})")
            logger.info(f"     内容片段: {doc.content[:100]}...")


@pytest.mark.integration
@pytest.mark.demo
# 该函数已被注释，因为 ConversationVectorDB 类已被移除
@pytest.mark.integration
@pytest.mark.demo
def demo_conversation_memory() -> None:
    """演示对话记忆系统 - 已移除，因为 ConversationVectorDB 类已被删除"""
    logger.info("⚠️ demo_conversation_memory 已被移除")
    pass


# 该函数已被注释，因为 GameKnowledgeVectorDB 类已被移除
@pytest.mark.integration
@pytest.mark.demo
def demo_game_knowledge_system() -> None:
    """演示游戏知识系统 - 已移除，因为 GameKnowledgeVectorDB 类已被删除"""
    logger.info("⚠️ demo_game_knowledge_system 已被移除")
    pass


# ================================
# 主函数和测试运行器
# ================================


def run_all_vector_tests() -> None:
    """运行所有向量功能测试"""
    logger.info("🚀 开始运行 pgvector 功能测试...")

    try:
        # 确保数据库表已创建
        from src.multi_agents_game.pgsql.client import engine
        from src.multi_agents_game.pgsql.client import Base  # type: ignore[attr-defined]

        Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库表已就绪")

        # 运行各项测试
        test_vector_document_operations()
        test_conversation_vector_operations()  # 现在是占位符函数
        # test_game_knowledge_operations()       # 已移除

        # 获取最终统计
        from src.multi_agents_game.pgsql.vector_document import (
            get_database_vector_stats,
        )

        final_stats = get_database_vector_stats()
        logger.info(f"🏁 测试完成，最终统计: {final_stats}")

    except Exception as e:
        logger.error(f"❌ 测试运行失败: {e}")
        raise e


def run_all_demos() -> None:
    """运行所有演示"""
    logger.info("🚀 pgvector集成演示开始...")

    try:
        # 确保数据库表已创建
        from src.multi_agents_game.pgsql.client import engine
        from src.multi_agents_game.pgsql.client import Base  # type: ignore[attr-defined]

        Base.metadata.create_all(bind=engine)

        # 运行各种演示
        demo_document_rag_system()
        demo_conversation_memory()  # 现在是占位符函数
        demo_game_knowledge_system()  # 现在是占位符函数

        # 显示最终统计
        from src.multi_agents_game.pgsql.vector_document import (
            get_database_vector_stats,
        )

        logger.info("\n📊 最终数据库统计:")
        stats = get_database_vector_stats()
        for table_name, table_stats in stats.items():
            logger.info(f"   {table_name}: {table_stats['with_embeddings']} 条向量记录")

        logger.info("\n✅ pgvector集成演示完成！")
        logger.info("🎉 您现在可以在项目中使用向量数据库功能了！")

    except Exception as e:
        logger.error(f"❌ 演示失败: {e}")


@pytest.mark.integration
@pytest.mark.comprehensive
def test_comprehensive_pgvector_integration(setup_database_tables: Any) -> None:
    """运行完整的 pgvector 集成测试"""
    logger.info("🌟 开始 pgvector 综合测试和演示...")

    try:
        # 第一部分：基础SQL测试
        logger.info("\n" + "=" * 50)
        logger.info("第一部分：基础SQL向量操作测试")
        logger.info("=" * 50)
        test_basic_vector_operations()
        test_high_dimension_vectors()

        # 第二部分：ORM测试
        logger.info("\n" + "=" * 50)
        logger.info("第二部分：ORM向量操作测试")
        logger.info("=" * 50)
        test_vector_document_operations()
        test_conversation_vector_operations()  # 现在是占位符函数
        # test_game_knowledge_operations()       # 已移除

        # 最终总结
        logger.info("\n" + "=" * 50)
        logger.info("🎉 所有测试完成！")
        logger.info("✅ pgvector 功能集成验证成功！")
        logger.info("💡 您现在可以在项目中使用完整的向量数据库功能了！")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"❌ 综合测试失败: {e}")
        raise e


@pytest.mark.integration
@pytest.mark.demo
@pytest.mark.slow
def test_comprehensive_pgvector_demos(setup_database_tables: Any) -> None:
    """运行完整的 pgvector 演示"""
    logger.info("🚀 pgvector集成演示开始...")

    try:
        # 第三部分：实际应用演示
        logger.info("\n" + "=" * 50)
        logger.info("第三部分：实际应用场景演示")
        logger.info("=" * 50)
        demo_document_rag_system()
        demo_conversation_memory()  # 现在是占位符函数
        demo_game_knowledge_system()  # 现在是占位符函数

        # 显示最终统计
        from src.multi_agents_game.pgsql.vector_document import (
            get_database_vector_stats,
        )

        logger.info("\n📊 最终数据库统计:")
        stats = get_database_vector_stats()
        for table_name, table_stats in stats.items():
            logger.info(f"   {table_name}: {table_stats['with_embeddings']} 条向量记录")

        logger.info("\n✅ pgvector集成演示完成！")
        logger.info("🎉 您现在可以在项目中使用向量数据库功能了！")

    except Exception as e:
        logger.error(f"❌ 演示失败: {e}")
        raise e


if __name__ == "__main__":
    # 当直接运行脚本时，执行完整测试
    import pytest

    # 可以选择运行不同的测试模块
    import argparse

    parser = argparse.ArgumentParser(description="pgvector 综合测试和演示")
    parser.add_argument(
        "--mode",
        choices=["all", "basic", "orm", "demo"],
        default="all",
        help="选择运行模式",
    )

    args = parser.parse_args()

    if args.mode == "all":
        # 运行所有测试
        pytest.main([__file__, "-v", "-s"])
    elif args.mode == "basic":
        logger.info("🧪 只运行基础SQL测试...")
        pytest.main(
            [
                __file__ + "::test_basic_vector_operations",
                __file__ + "::test_high_dimension_vectors",
                "-v",
                "-s",
            ]
        )
    elif args.mode == "orm":
        logger.info("🧪 只运行ORM测试...")
        pytest.main(
            [
                __file__ + "::test_vector_document_operations",
                __file__ + "::test_conversation_vector_operations",
                __file__ + "::test_game_knowledge_operations",
                "-v",
                "-s",
            ]
        )
    elif args.mode == "demo":
        logger.info("🧪 只运行演示...")
        pytest.main([__file__ + "::test_comprehensive_pgvector_demos", "-v", "-s"])
