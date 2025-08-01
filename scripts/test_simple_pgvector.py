"""
pgvector 功能的简化测试
验证基本的向量保存和检索功能
"""

import numpy as np
from typing import List
from sqlalchemy import create_engine, text
from loguru import logger
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入配置
from src.multi_agents_game.config.db_config import POSTGRES_DATABASE_URL


def test_basic_vector_operations():
    """测试基本的向量操作"""
    logger.info("🧪 开始测试基本向量操作...")

    # 创建数据库连接
    engine = create_engine(POSTGRES_DATABASE_URL)

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


def test_high_dimension_vectors():
    """测试高维向量（1536维）"""
    logger.info("🧪 开始测试高维向量操作...")

    engine = create_engine(POSTGRES_DATABASE_URL)

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


if __name__ == "__main__":
    test_basic_vector_operations()
    test_high_dimension_vectors()
