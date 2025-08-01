"""
pgvector 功能测试和使用示例
展示如何使用向量数据库进行文档存储、检索和相似度搜索
"""

import numpy as np
from typing import List
from loguru import logger

# 模拟OpenAI嵌入API的函数 (实际使用时需要连接真实的API)
def mock_get_embedding(text: str) -> List[float]:
    """
    模拟获取文本嵌入向量的函数
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
    return vector.tolist()


def test_vector_document_operations():
    """测试向量文档操作"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.multi_agents_game.db.pgsql_vector_ops import (
        save_vector_document, 
        search_similar_documents,
        get_database_vector_stats
    )
    
    logger.info("🧪 开始测试向量文档操作...")
    
    # 1. 保存一些测试文档
    test_documents = [
        {
            "content": "这是一个关于机器学习的基础教程，介绍了监督学习和无监督学习的基本概念。",
            "title": "机器学习基础",
            "doc_type": "tutorial",
            "source": "ml_guide.md"
        },
        {
            "content": "深度学习是机器学习的一个分支，使用神经网络来模拟人脑的学习过程。",
            "title": "深度学习介绍", 
            "doc_type": "tutorial",
            "source": "dl_intro.md"
        },
        {
            "content": "Python是一种高级编程语言，广泛用于数据科学、机器学习和Web开发。",
            "title": "Python编程入门",
            "doc_type": "programming",
            "source": "python_basics.md"
        },
        {
            "content": "数据库设计是软件开发中的重要环节，需要考虑数据的结构化存储和查询效率。",
            "title": "数据库设计原则",
            "doc_type": "database",
            "source": "db_design.md"
        }
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
                metadata={"test": True, "category": doc_data["doc_type"]}
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
            similarity_threshold=0.0  # 降低阈值以便看到结果
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
            similarity_threshold=0.0
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


def test_conversation_vector_operations():
    """测试对话向量操作"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.multi_agents_game.db.pgsql_vector_ops import (
        save_conversation_vector,
        search_similar_conversations
    )
    from uuid import uuid4
    
    logger.info("🧪 开始测试对话向量操作...")
    
    # 模拟游戏会话ID
    game_session_id = uuid4()
    
    # 1. 保存一些测试对话
    test_conversations = [
        {
            "content": "玩家请求查看当前的游戏状态和可用行动",
            "sender": "player_1",
            "receiver": "game_master",
            "message_type": "player_request"
        },
        {
            "content": "游戏主持回应：你现在在森林中，可以选择向北、向南或者停留",
            "sender": "game_master", 
            "receiver": "player_1",
            "message_type": "game_response"
        },
        {
            "content": "玩家决定向北前进探索新区域",
            "sender": "player_1",
            "receiver": "game_master",
            "message_type": "player_action"
        },
        {
            "content": "遇到了一群友善的精灵，他们愿意提供帮助",
            "sender": "game_master",
            "receiver": "player_1", 
            "message_type": "game_event"
        }
    ]
    
    saved_conversations = []
    for conv_data in test_conversations:
        try:
            # 生成嵌入向量
            embedding = mock_get_embedding(conv_data["content"])
            
            # 保存到数据库
            conv = save_conversation_vector(
                message_content=conv_data["content"],
                embedding=embedding,
                sender=conv_data["sender"],
                receiver=conv_data["receiver"],
                message_type=conv_data["message_type"],
                game_session_id=game_session_id
            )
            saved_conversations.append(conv)
            logger.info(f"✅ 已保存对话: {conv_data['message_type']}")
            
        except Exception as e:
            logger.error(f"❌ 保存对话失败: {e}")
    
    # 2. 测试对话搜索
    try:
        query_text = "玩家想要探索和移动"
        query_embedding = mock_get_embedding(query_text)
        
        logger.info(f"🔍 搜索相似对话: {query_text}")
        
        # 搜索相似对话
        similar_convs = search_similar_conversations(
            query_embedding=query_embedding,
            limit=3,
            game_session_id=game_session_id,
            similarity_threshold=0.0
        )
        
        logger.info(f"💬 找到 {len(similar_convs)} 个相似对话:")
        for conv, similarity in similar_convs:
            logger.info(f"  - {conv.message_type}: 相似度 {similarity:.4f}")
            logger.info(f"    内容: {conv.message_content[:50]}...")
            
    except Exception as e:
        logger.error(f"❌ 对话搜索失败: {e}")


def test_game_knowledge_operations():
    """测试游戏知识向量操作"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.multi_agents_game.db.pgsql_vector_ops import (
        save_game_knowledge_vector,
        search_game_knowledge
    )
    
    logger.info("🧪 开始测试游戏知识向量操作...")
    
    # 1. 保存一些测试游戏知识
    test_knowledge = [
        {
            "content": "在RPG游戏中，角色属性包括力量、敏捷、智力和体力，这些属性影响战斗能力",
            "title": "RPG角色属性系统",
            "category": "game_mechanics",
            "game_type": "rpg",
            "difficulty": 1,
            "tags": ["属性", "角色", "战斗"]
        },
        {
            "content": "卡牌游戏的基本策略是平衡资源管理和攻击时机，需要考虑手牌数量和法力值",
            "title": "卡牌游戏基础策略",
            "category": "strategy",
            "game_type": "card_game", 
            "difficulty": 2,
            "tags": ["策略", "资源", "时机"]
        },
        {
            "content": "多人合作游戏中，团队沟通和角色分工是获胜的关键要素",
            "title": "多人合作技巧",
            "category": "teamwork",
            "game_type": "multiplayer",
            "difficulty": 3,
            "tags": ["合作", "沟通", "团队"]
        }
    ]
    
    saved_knowledge = []
    for knowledge_data in test_knowledge:
        try:
            # 生成嵌入向量
            embedding = mock_get_embedding(knowledge_data["content"])
            
            # 保存到数据库
            knowledge = save_game_knowledge_vector(
                knowledge_content=knowledge_data["content"],
                embedding=embedding,
                title=knowledge_data["title"],
                knowledge_category=knowledge_data["category"],
                game_type=knowledge_data["game_type"],
                difficulty_level=knowledge_data["difficulty"],
                tags=knowledge_data["tags"],
                priority=knowledge_data["difficulty"]  # 难度越高优先级越高
            )
            saved_knowledge.append(knowledge)
            logger.info(f"✅ 已保存游戏知识: {knowledge.title}")
            
        except Exception as e:
            logger.error(f"❌ 保存游戏知识失败: {e}")
    
    # 2. 测试知识搜索
    try:
        query_text = "如何在游戏中提升角色战斗力"
        query_embedding = mock_get_embedding(query_text)
        
        logger.info(f"🔍 搜索游戏知识: {query_text}")
        
        # 搜索相关知识
        relevant_knowledge = search_game_knowledge(
            query_embedding=query_embedding,
            limit=3,
            max_difficulty=2,  # 只搜索难度2级以下的知识
            similarity_threshold=0.0
        )
        
        logger.info(f"🎮 找到 {len(relevant_knowledge)} 个相关知识:")
        for knowledge, similarity in relevant_knowledge:
            logger.info(f"  - {knowledge.title}: 相似度 {similarity:.4f}, 难度 {knowledge.difficulty_level}")
            logger.info(f"    内容: {knowledge.knowledge_content[:50]}...")
            
    except Exception as e:
        logger.error(f"❌ 游戏知识搜索失败: {e}")


def run_all_vector_tests():
    """运行所有向量功能测试"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    logger.info("🚀 开始运行 pgvector 功能测试...")
    
    try:
        # 确保数据库表已创建
        from src.multi_agents_game.db.pgsql_client import Base, engine
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库表已就绪")
        
        # 运行各项测试
        test_vector_document_operations()
        test_conversation_vector_operations()
        test_game_knowledge_operations()
        
        # 获取最终统计
        from src.multi_agents_game.db.pgsql_vector_ops import get_database_vector_stats
        final_stats = get_database_vector_stats()
        logger.info(f"🏁 测试完成，最终统计: {final_stats}")
        
    except Exception as e:
        logger.error(f"❌ 测试运行失败: {e}")
        raise e


if __name__ == "__main__":
    run_all_vector_tests()
