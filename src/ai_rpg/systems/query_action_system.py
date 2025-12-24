from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor

# from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    QueryAction,
)
from loguru import logger
from loguru import logger
from ..embedding_model import (
    multilingual_model,
)
from ..chroma import get_default_collection, get_private_knowledge_collection
from ..rag import search_similar_documents, search_private_knowledge
from ..game.tcg_game import TCGGame


#####################################################################################################################################
@final
class QueryActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

    #############################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(QueryAction): GroupEvent.ADDED}

    #############################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(QueryAction)

    #############################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    #############################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        query_action = entity.get(QueryAction)
        assert query_action is not None

        related_info = self._get_related_info(entity, query_action.question)
        logger.success(f"🔎 角色发起查询行动，问题: {query_action.question}")
        logger.success(f"💭 角色记忆查询结果: {related_info}")

        if related_info:
            self._game.add_human_message(
                entity,
                f"经过回忆，这些是你回忆到的信息：\n{related_info}\n\n选择性地将这些信息作为参考。如果最近一次的行动计划里执行了查询行动，下一次的行动计划禁止再次进行查询行动，除非遇到全新未曾查询过的问题。",
            )
        else:
            self._game.add_human_message(
                entity,
                "没有找到相关背景信息。在接下来的对话中，如果涉及没有找到的或者不在你的上下文中的内容，请诚实地表示不知道，不要编造.",
            )

    ####################################################################################################################################
    def _get_related_info(self, entity: Entity, original_message: str) -> str:
        """检索相关信息 - 双层查询（公共知识 + 私有知识）"""
        try:
            logger.success(f"🔍 双层RAG检索: {original_message}")

            # 执行双层RAG检索
            return self._query_with_rag(entity, original_message)

        except Exception as e:
            logger.error(f"❌ 相关信息检索失败: {e}")
            return ""  # 失败时返回空

    ####################################################################################################################################
    def _query_with_rag(self, entity: Entity, message: str) -> str:
        """RAG查询处理 - 双层查询（公共知识 + 私有知识）"""
        try:
            logger.debug(f"🔍 RAG查询: {message}...")

            result_parts = []

            # 1. 查询公共知识（default_collection）
            logger.info("📚 查询公共知识库...")
            public_docs, public_scores = search_similar_documents(
                query=message,
                collection=get_default_collection(),
                embedding_model=multilingual_model,
                top_k=3,
            )

            if public_docs:
                result_parts.append("【公共知识】")
                for i, (doc, score) in enumerate(zip(public_docs, public_scores), 1):
                    result_parts.append(f"{i}. [相似度: {score:.3f}] {doc}")
                logger.success(f"✅ 找到 {len(public_docs)} 条公共知识")

            # 2. 查询私有知识（private_knowledge_collection + where 过滤）
            logger.info(f"🔐 查询 {entity.name} 的私有知识库...")
            private_docs, private_scores = search_private_knowledge(
                query=message,
                character_name=entity.name,  # ← 关键：使用角色名过滤
                collection=get_private_knowledge_collection(),
                embedding_model=multilingual_model,
                top_k=3,
            )

            if private_docs:
                if result_parts:  # 如果已有公共知识，添加分隔
                    result_parts.append("")
                result_parts.append("【私有知识（你的记忆）】")
                for i, (doc, score) in enumerate(zip(private_docs, private_scores), 1):
                    result_parts.append(f"{i}. [相似度: {score:.3f}] {doc}")
                logger.success(f"✅ 找到 {len(private_docs)} 条私有知识")

            # 3. 检查查询结果
            if not result_parts:
                logger.warning("⚠️ 未检索到任何相关文档，返回空结果")
                return ""

            # 4. 格式化并返回结果
            query_result = "\n".join(result_parts)
            total_docs = len(public_docs) + len(private_docs)
            logger.success(
                f"🔍 RAG查询完成，共找到 {total_docs} 条相关知识（公共: {len(public_docs)}, 私有: {len(private_docs)}）"
            )

            return query_result

        except Exception as e:
            logger.error(f"❌ RAG查询失败: {e}")
            return ""


#####################################################################################################################################
