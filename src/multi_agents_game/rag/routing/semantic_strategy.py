"""
语义路由策略

基于语义相似度的路由决策策略，使用SentenceTransformers进行语义匹配。
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from .route_strategy import RouteDecision, RouteStrategy


class SemanticRouteStrategy(RouteStrategy):
    """基于语义相似度的路由策略"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("semantic_matcher", config)
        self.model = None
        self.rag_topics: List[str] = []
        self.topic_embeddings = None
        self.similarity_threshold = self.get_config_value("similarity_threshold", 0.6)
        self.use_multilingual = self.get_config_value("use_multilingual", True)

    def _do_initialize(self) -> None:
        """初始化语义模型和主题向量"""
        try:
            # 加载模型
            if self.use_multilingual:
                from ...embedding_model.model_loader import load_multilingual_model

                self.model = load_multilingual_model()
                model_name = "multilingual"
            else:
                from ...embedding_model.model_loader import load_basic_model

                self.model = load_basic_model()
                model_name = "basic"

            if self.model is None:
                raise RuntimeError("语义模型加载失败")

            # 预定义的RAG相关主题
            self.rag_topics = self.get_config_value(
                "rag_topics",
                [
                    "游戏世界设定和背景知识",
                    "角色信息和人物介绍",
                    # "装备道具和物品详情",
                    # "地图位置和场景描述",
                    # "技能魔法和战斗系统",
                    # "剧情故事和历史背景",
                    # "组织势力和政治关系",
                    # "种族文化和社会结构",
                ],
            )

            # 计算主题嵌入向量
            self.topic_embeddings = self.model.encode(self.rag_topics)

            logger.success(
                f"🧠 语义路由策略初始化完成: {model_name}模型, "
                f"{len(self.rag_topics)}个主题, 相似度阈值={self.similarity_threshold}"
            )

        except Exception as e:
            logger.error(f"🧠 语义路由策略初始化失败: {e}")
            raise

    def should_route_to_rag(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> RouteDecision:
        """基于语义相似度进行路由决策"""
        if not self.is_initialized:
            self.initialize()

        if self.model is None or self.topic_embeddings is None:
            logger.warning("🧠 语义模型未就绪，回退到低置信度决策")
            return RouteDecision(
                should_use_rag=False,
                confidence=0.1,
                strategy_name=self.name,
                metadata={"error": "model_not_ready"},
            )

        try:
            # 计算查询向量
            query_embedding = self.model.encode([query])

            # 计算与各主题的相似度
            from sentence_transformers.util import cos_sim

            similarities = cos_sim(query_embedding, self.topic_embeddings)[0]

            # 获取最高相似度
            max_similarity = float(similarities.max().item())
            best_topic_idx = int(similarities.argmax().item())
            best_topic = self.rag_topics[best_topic_idx]

            # 基于阈值做决策
            should_use_rag = max_similarity >= self.similarity_threshold

            # 置信度就是相似度本身
            confidence = max_similarity

            logger.debug(
                f"🧠 语义匹配: 最高相似度 {max_similarity:.3f} "
                f"(主题: {best_topic[:20]}...), 阈值 {self.similarity_threshold}"
            )

            return RouteDecision(
                should_use_rag=should_use_rag,
                confidence=confidence,
                strategy_name=self.name,
                metadata={
                    "max_similarity": max_similarity,
                    "best_topic": best_topic,
                    "best_topic_index": best_topic_idx,
                    "threshold": self.similarity_threshold,
                    "all_similarities": similarities.tolist(),
                },
            )

        except Exception as e:
            logger.error(f"🧠 语义匹配过程出错: {e}")
            return RouteDecision(
                should_use_rag=False,
                confidence=0.1,
                strategy_name=self.name,
                metadata={"error": str(e)},
            )
