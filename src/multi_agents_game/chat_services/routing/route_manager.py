"""
路由决策管理器

组合多个路由策略，提供统一的路由决策接口。
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger

from .route_strategy import FallbackRouteStrategy, RouteDecision, RouteStrategy


@dataclass
class StrategyWeight:
    """策略权重配置"""

    strategy: RouteStrategy
    weight: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"权重必须在 0.0-1.0 之间，当前值: {self.weight}")


class RouteDecisionManager:
    """路由决策管理器 - 组合多个策略进行决策"""

    def __init__(
        self,
        strategy_weights: List[StrategyWeight],
        fallback_strategy: Optional[RouteStrategy] = None,
    ):
        """
        初始化路由决策管理器

        Args:
            strategy_weights: 策略和权重配置列表
            fallback_strategy: 回退策略，当所有策略都失败时使用
        """
        self.strategy_weights = strategy_weights
        self.fallback_strategy = fallback_strategy or FallbackRouteStrategy(
            default_to_rag=False
        )

        # 验证权重总和
        total_weight = sum(sw.weight for sw in strategy_weights)
        if not 0.95 <= total_weight <= 1.05:  # 允许一点浮点误差
            logger.warning(f"⚠️ 策略权重总和不等于1.0: {total_weight}")

    def make_decision(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> RouteDecision:
        """
        进行路由决策

        Args:
            query: 用户查询
            context: 可选的上下文信息

        Returns:
            RouteDecision: 最终的路由决策
        """
        logger.info(f"🎯 开始路由决策，查询: {query[:50]}...")

        decisions = []
        total_weighted_confidence = 0.0
        total_weighted_rag_votes = 0.0

        # 收集所有策略的决策
        for strategy_weight in self.strategy_weights:
            try:
                decision = strategy_weight.strategy.should_route_to_rag(query, context)
                decisions.append((decision, strategy_weight.weight))

                # 计算加权置信度和RAG投票
                weighted_confidence = decision.confidence * strategy_weight.weight
                total_weighted_confidence += weighted_confidence

                if decision.should_use_rag:
                    total_weighted_rag_votes += strategy_weight.weight

                logger.debug(
                    f"  📊 {decision.strategy_name}: RAG={decision.should_use_rag}, "
                    f"置信度={decision.confidence:.3f}, 权重={strategy_weight.weight}"
                )

            except Exception as e:
                logger.error(f"❌ 策略 {strategy_weight.strategy.name} 执行失败: {e}")
                continue

        # 如果没有有效决策，使用回退策略
        if not decisions:
            logger.warning("⚠️ 所有策略都失败，使用回退策略")
            return self.fallback_strategy.should_route_to_rag(query, context)

        # 组合决策：基于加权投票
        final_should_use_rag = total_weighted_rag_votes > 0.5
        final_confidence = total_weighted_confidence

        # 准备元数据
        strategy_names = [d[0].strategy_name for d in decisions]
        individual_decisions = {
            d[0].strategy_name: {
                "should_use_rag": d[0].should_use_rag,
                "confidence": d[0].confidence,
                "weight": d[1],
                "metadata": d[0].metadata,
            }
            for d in decisions
        }

        final_decision = RouteDecision(
            should_use_rag=final_should_use_rag,
            confidence=final_confidence,
            strategy_name="combined",
            metadata={
                "strategies_used": strategy_names,
                "weighted_rag_votes": total_weighted_rag_votes,
                "total_strategies": len(decisions),
                "individual_decisions": individual_decisions,
            },
        )

        logger.success(
            f"🎯 路由决策完成: RAG={final_should_use_rag}, "
            f"置信度={final_confidence:.3f}, 使用策略={len(decisions)}个"
        )

        return final_decision


class RouteConfigBuilder:
    """路由配置构建器 - 提供便捷的配置方法"""

    def __init__(self) -> None:
        self.strategy_weights: List[StrategyWeight] = []
        self.fallback_strategy: Optional[RouteStrategy] = None

    def add_strategy(
        self, strategy: RouteStrategy, weight: float
    ) -> "RouteConfigBuilder":
        """添加策略"""
        self.strategy_weights.append(StrategyWeight(strategy, weight))
        return self

    def set_fallback(self, strategy: RouteStrategy) -> "RouteConfigBuilder":
        """设置回退策略"""
        self.fallback_strategy = strategy
        return self

    def build(self) -> RouteDecisionManager:
        """构建路由决策管理器"""
        return RouteDecisionManager(self.strategy_weights, self.fallback_strategy)


def create_route_manager_with_strategies(
    strategy_configs: List[Tuple[Callable[[], RouteStrategy], float]],
    fallback_to_rag: bool = False,
) -> RouteDecisionManager:
    """
    创建带有指定策略配置的路由决策管理器（核心参数化函数）

    Args:
        strategy_configs: 策略配置列表，每个元素是 (策略创建函数, 权重) 的元组
        fallback_to_rag: 回退策略是否默认使用RAG

    Returns:
        RouteDecisionManager: 配置好的路由决策管理器

    Example:
        >>> from .keyword_strategy import create_alphania_keyword_strategy
        >>> from .semantic_strategy import create_game_semantic_strategy
        >>>
        >>> manager = create_route_manager_with_strategies([
        ...     (create_alphania_keyword_strategy, 0.4),
        ...     (create_game_semantic_strategy, 0.6),
        ... ], fallback_to_rag=False)
    """
    builder = RouteConfigBuilder()

    # 添加所有策略配置
    for strategy_factory, weight in strategy_configs:
        strategy = strategy_factory()
        builder.add_strategy(strategy, weight)

    # 设置回退策略
    fallback_strategy = FallbackRouteStrategy(default_to_rag=fallback_to_rag)
    builder.set_fallback(fallback_strategy)

    return builder.build()


def create_default_route_manager() -> RouteDecisionManager:
    """创建默认的路由决策管理器"""
    from .keyword_strategy import create_alphania_keyword_strategy
    from .semantic_strategy import create_game_semantic_strategy

    # 使用参数化的核心函数创建默认配置
    return create_route_manager_with_strategies(
        strategy_configs=[
            (create_alphania_keyword_strategy, 0.4),
            (create_game_semantic_strategy, 0.6),
        ],
        fallback_to_rag=False,
    )
