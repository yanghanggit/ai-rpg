from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher, InitializeProcessor
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    QueryAction,
)
from loguru import logger
from ..rag.routing import (
    KeywordRouteStrategy,
    SemanticRouteStrategy,
    RouteDecisionManager,
    FallbackRouteStrategy,
    RouteConfigBuilder,
)
from ..demo.campaign_setting import (
    FANTASY_WORLD_RPG_TEST_ROUTE_KEYWORDS,
    FANTASY_WORLD_RPG_TEST_RAG_TOPICS,
)
from ..chroma import get_chroma_db
from ..rag import search_similar_documents
from ..embedding_model.sentence_transformer import get_embedding_model
from loguru import logger
from ..game.tcg_game import TCGGame


#####################################################################################################################################
@final
class QueryActionSystem(BaseActionReactiveSystem, InitializeProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._route_manager: RouteDecisionManager | None = None

    #############################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(QueryAction): GroupEvent.ADDED}

    #############################################################################################################################
    @override
    async def initialize(self) -> None:
        """初始化处理器"""
        if self._route_manager is None:
            self._initialize_route_system()
        logger.debug("🚀 MindVoiceActionSystem 初始化完成")

    ####################################################################################################################################
    def _initialize_route_system(self) -> None:
        """初始化路由系统"""
        try:
            # 创建关键词策略
            keyword_config = {
                "keywords": FANTASY_WORLD_RPG_TEST_ROUTE_KEYWORDS,
                "threshold": 0.05,  # 降低阈值：只要匹配到关键词就触发RAG
                "case_sensitive": False,
            }
            keyword_strategy = KeywordRouteStrategy(keyword_config)

            # 创建语义策略
            semantic_config = {
                "similarity_threshold": 0.4,  # 降低相似度阈值：0.488 > 0.4
                "use_multilingual": True,
                "rag_topics": FANTASY_WORLD_RPG_TEST_RAG_TOPICS,
            }
            semantic_strategy = SemanticRouteStrategy(semantic_config)

            # 创建路由管理器
            builder = RouteConfigBuilder()
            builder.add_strategy(keyword_strategy, 0.4)
            builder.add_strategy(semantic_strategy, 0.6)
            builder.set_fallback(FallbackRouteStrategy(default_to_rag=False))

            self._route_manager = builder.build()

            logger.debug("🎯 MindVoiceActionSystem 路由系统初始化完成")

        except Exception as e:
            logger.error(f"❌ MindVoiceActionSystem 路由系统初始化失败: {e}")
            self._route_manager = None

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

        related_info = self._get_related_info(query_action.question)
        logger.success(f"🔎 角色发起查询行动，问题: {query_action.question}")
        logger.debug(f"💭 内心独白查询结果: {related_info}")

        if related_info:
            self._game.append_human_message(
                entity,
                f"基于以下回忆出来的信息回答问题或回复对话：\n{related_info}\n\n选择你认为最合适的信息出来作为参考来回答问题。",
            )
        else:
            self._game.append_human_message(
                entity,
                "没有找到相关背景信息。在接下来的对话中，如果涉及没有找到的或者不在你的上下文中的内容，请诚实地表示不知道，不要编造。",
            )

    ####################################################################################################################################
    def _get_related_info(self, original_message: str) -> str:
        """检索相关信息 - 直接进行检索，能找到就返回，找不到就返回空"""
        try:
            logger.success(f"🔍 直接进行RAG检索: {original_message}")

            # 直接执行RAG检索，不需要路由决策
            return self._query_with_rag(original_message)

        except Exception as e:
            logger.error(f"❌ 相关信息检索失败: {e}")
            return ""  # 失败时返回空

    ####################################################################################################################################
    def _query_with_rag(self, message: str) -> str:
        """RAG查询处理 - 仅执行查询并返回结果"""
        try:
            logger.debug(f"🔍 RAG查询: {message}...")

            # 1. 检查ChromaDB状态
            chroma_db = get_chroma_db()
            if not chroma_db.initialized:
                logger.warning("⚠️ ChromaDB未初始化，返回空结果")
                return ""

            # 1.5. 获取嵌入模型
            embedding_model = get_embedding_model()
            if embedding_model is None:
                logger.warning("⚠️ 嵌入模型未初始化，返回空结果")
                return ""

            # 1.6. 检查collection是否可用
            if chroma_db.collection is None:
                logger.warning("⚠️ ChromaDB collection未初始化，返回空结果")
                return ""

            # 2. 执行语义搜索查询
            retrieved_docs, similarity_scores = search_similar_documents(
                query=message,
                collection=chroma_db.collection,
                embedding_model=embedding_model,
                top_k=3,
            )

            # 3. 检查查询结果
            if not retrieved_docs:
                logger.warning("⚠️ 未检索到相关文档，返回空结果")
                return ""

            # 4. 简单格式化查询结果并返回
            result_parts = []
            for i, (doc, score) in enumerate(zip(retrieved_docs, similarity_scores), 1):
                result_parts.append(f"{i}. [相似度: {score:.3f}] {doc}")

            query_result = "\n".join(result_parts)
            logger.success(f"🔍 RAG查询完成，找到 {len(retrieved_docs)} 个相关文档")

            return query_result

        except Exception as e:
            logger.error(f"❌ RAG查询失败: {e}")
            return ""
