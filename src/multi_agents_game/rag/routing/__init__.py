"""
路由决策模块

提供可配置的、可扩展的聊天路由决策功能，支持多种策略组合。

主要组件：
- RouteStrategy: 路由策略抽象基类
- KeywordRouteStrategy: 基于关键词的路由策略
- SemanticRouteStrategy: 基于语义相似度的路由策略
- RouteDecisionManager: 路由决策管理器，组合多种策略

使用示例：
    # 创建默认路由管理器
    route_manager = create_default_route_manager()

    # 进行路由决策
    decision = route_manager.make_decision("艾尔法尼亚的王国有哪些？")

    if decision.should_use_rag:
        print("使用RAG模式")
    else:
        print("使用直接对话模式")
"""

from .keyword_strategy import KeywordRouteStrategy
from .route_manager import (
    RouteConfigBuilder,
    RouteDecisionManager,
    StrategyWeight,
    create_route_manager_with_strategies,
)
from .route_strategy import FallbackRouteStrategy, RouteDecision, RouteStrategy
from .semantic_strategy import SemanticRouteStrategy

__all__ = [
    # 基础类
    "RouteStrategy",
    "RouteDecision",
    "FallbackRouteStrategy",
    # 具体策略
    "KeywordRouteStrategy",
    "SemanticRouteStrategy",
    # 管理器
    "RouteDecisionManager",
    "StrategyWeight",
    "RouteConfigBuilder",
    # 便捷函数
    "create_route_manager_with_strategies",
]
