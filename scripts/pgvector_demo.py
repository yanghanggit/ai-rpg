"""
pgvector 集成完成 - 使用示例和说明文档
"""

from typing import List, Dict, Any
import numpy as np
from loguru import logger

# 如果您有OpenAI API key，可以使用真实的嵌入API
# from openai import OpenAI
# client = OpenAI(api_key="your-api-key-here")

def mock_openai_embedding(text: str) -> List[float]:
    """
    模拟OpenAI嵌入API
    实际使用时，替换为真实的OpenAI API调用
    """
    # 使用文本哈希生成确定性向量
    import hashlib
    hash_obj = hashlib.md5(text.encode())
    seed = int(hash_obj.hexdigest(), 16) % (2**32)
    
    np.random.seed(seed)
    vector = np.random.randn(1536).astype(float)
    vector = vector / np.linalg.norm(vector)  # 归一化
    return vector.tolist()


def demo_document_rag_system():
    """演示基于文档的RAG系统"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.multi_agents_game.db.pgsql_vector_ops import (
        save_vector_document, 
        search_similar_documents
    )
    
    logger.info("🤖 演示文档RAG系统...")
    
    # 1. 保存一些知识文档
    documents = [
        {
            "title": "机器学习基础",
            "content": "机器学习是人工智能的一个分支，它让计算机能够在没有明确编程的情况下学习。主要包括监督学习、无监督学习和强化学习三种类型。",
            "doc_type": "knowledge",
            "source": "ml_textbook.pdf"
        },
        {
            "title": "深度学习原理", 
            "content": "深度学习使用多层神经网络来模拟人脑的工作方式。它在图像识别、自然语言处理等领域取得了突破性进展。",
            "doc_type": "knowledge",
            "source": "dl_guide.pdf"
        },
        {
            "title": "Python数据科学",
            "content": "Python是数据科学领域最流行的编程语言。主要库包括NumPy、Pandas、Matplotlib和Scikit-learn等。",
            "doc_type": "tutorial",
            "source": "python_ds.md"
        },
        {
            "title": "向量数据库应用",
            "content": "向量数据库用于存储和检索高维向量数据，特别适用于相似性搜索、推荐系统和RAG应用。",
            "doc_type": "knowledge", 
            "source": "vector_db.pdf"
        }
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
            metadata={"category": "knowledge_base"}
        )
    
    # 2. 模拟用户查询
    queries = [
        "什么是机器学习？",
        "如何使用Python进行数据分析？",
        "向量数据库有什么用途？",
        "深度学习和机器学习的区别是什么？"
    ]
    
    logger.info("🔍 处理用户查询...")
    for query in queries:
        logger.info(f"\n❓ 用户问题: {query}")
        
        # 获取查询的嵌入向量
        query_embedding = mock_openai_embedding(query)
        
        # 搜索相关文档
        results = search_similar_documents(
            query_embedding=query_embedding,
            limit=2,
            similarity_threshold=0.1
        )
        
        logger.info("📖 相关文档:")
        for doc, similarity in results:
            logger.info(f"   - {doc.title} (相似度: {similarity:.3f})")
            logger.info(f"     内容片段: {doc.content[:100]}...")


def demo_conversation_memory():
    """演示对话记忆系统"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.multi_agents_game.db.pgsql_vector_ops import (
        save_conversation_vector,
        search_similar_conversations
    )
    from uuid import uuid4
    
    logger.info("💬 演示对话记忆系统...")
    
    # 模拟游戏会话
    session_id = uuid4()
    
    # 保存一些对话历史
    conversations = [
        {
            "content": "我想学习如何在游戏中提升角色的战斗能力",
            "sender": "player_001",
            "message_type": "player_question"
        },
        {
            "content": "你可以通过升级装备、提高属性点和学习新技能来增强战斗力",
            "sender": "ai_assistant",
            "message_type": "assistant_response"
        },
        {
            "content": "请帮我制定一个角色发展策略",
            "sender": "player_001", 
            "message_type": "player_request"
        },
        {
            "content": "建议优先提升核心属性，然后获取适合你职业的装备和技能",
            "sender": "ai_assistant",
            "message_type": "assistant_advice"
        }
    ]
    
    logger.info("💾 保存对话历史...")
    for conv in conversations:
        embedding = mock_openai_embedding(conv["content"])
        save_conversation_vector(
            message_content=conv["content"],
            embedding=embedding,
            sender=conv["sender"],
            message_type=conv["message_type"],
            game_session_id=session_id
        )
    
    # 查询相似对话
    query = "如何提升游戏角色实力？"
    logger.info(f"\n🔍 查询相似对话: {query}")
    
    query_embedding = mock_openai_embedding(query)
    similar_convs = search_similar_conversations(
        query_embedding=query_embedding,
        limit=3,
        game_session_id=session_id,
        similarity_threshold=0.1
    )
    
    logger.info("🗨️ 相似的历史对话:")
    for conv, similarity in similar_convs:
        logger.info(f"   - {conv.sender}: {conv.message_content[:50]}... (相似度: {similarity:.3f})")


def demo_game_knowledge_system():
    """演示游戏知识系统"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.multi_agents_game.db.pgsql_vector_ops import (
        save_game_knowledge_vector,
        search_game_knowledge
    )
    
    logger.info("🎮 演示游戏知识系统...")
    
    # 保存游戏知识
    knowledge_items = [
        {
            "title": "RPG角色属性系统",
            "content": "RPG游戏中，角色通常有力量、敏捷、智力、体力等基础属性。力量影响物理攻击，敏捷影响速度和暴击，智力影响魔法威力，体力影响生命值。",
            "category": "game_mechanics",
            "game_type": "rpg",
            "difficulty": 1,
            "tags": ["属性", "角色", "基础"]
        },
        {
            "title": "战斗策略基础",
            "content": "有效的战斗策略包括：了解敌人弱点、合理使用技能冷却、保持距离控制、团队配合等。需要根据不同敌人类型调整战术。",
            "category": "strategy",
            "game_type": "rpg",
            "difficulty": 2,
            "tags": ["战斗", "策略", "技巧"]
        },
        {
            "title": "装备强化系统",
            "content": "装备强化可以提升装备的基础属性。通常需要消耗强化石和金币。强化等级越高，成功率越低，但属性提升越明显。",
            "category": "equipment",
            "game_type": "rpg", 
            "difficulty": 2,
            "tags": ["装备", "强化", "属性"]
        }
    ]
    
    logger.info("📖 保存游戏知识...")
    for knowledge in knowledge_items:
        embedding = mock_openai_embedding(knowledge["content"])
        save_game_knowledge_vector(
            knowledge_content=knowledge["content"],
            embedding=embedding,
            title=knowledge["title"],
            knowledge_category=knowledge["category"],
            game_type=knowledge["game_type"],
            difficulty_level=knowledge["difficulty"],
            tags=knowledge["tags"],
            priority=knowledge["difficulty"]
        )
    
    # 查询游戏知识
    queries = [
        "如何提升角色的攻击力？",
        "战斗中需要注意什么？",
        "装备要怎么强化？"
    ]
    
    for query in queries:
        logger.info(f"\n❓ 玩家问题: {query}")
        query_embedding = mock_openai_embedding(query)
        
        knowledge_results = search_game_knowledge(
            query_embedding=query_embedding,
            limit=2,
            game_type_filter="rpg",
            max_difficulty=2,
            similarity_threshold=0.1
        )
        
        logger.info("💡 相关知识:")
        for knowledge, similarity in knowledge_results:
            logger.info(f"   - {knowledge.title} (相似度: {similarity:.3f})")
            logger.info(f"     知识: {knowledge.knowledge_content[:80]}...")


def main():
    """运行所有演示"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    logger.info("🚀 pgvector集成演示开始...")
    
    try:
        # 确保数据库表已创建
        from src.multi_agents_game.db.pgsql_client import Base, engine
        Base.metadata.create_all(bind=engine)
        
        # 运行各种演示
        demo_document_rag_system()
        demo_conversation_memory()
        demo_game_knowledge_system()
        
        # 显示最终统计
        from src.multi_agents_game.db.pgsql_vector_ops import get_database_vector_stats
        logger.info("\n📊 最终数据库统计:")
        stats = get_database_vector_stats()
        for table_name, table_stats in stats.items():
            logger.info(f"   {table_name}: {table_stats['with_embeddings']} 条向量记录")
        
        logger.info("\n✅ pgvector集成演示完成！")
        logger.info("🎉 您现在可以在项目中使用向量数据库功能了！")
        
    except Exception as e:
        logger.error(f"❌ 演示失败: {e}")


if __name__ == "__main__":
    main()
