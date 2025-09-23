"""
路由策略接口和基类

定义了路由决策的抽象接口，支持多种路由策略的实现。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from loguru import logger


@dataclass
class RouteDecision:
    """路由决策结果"""

    should_use_rag: bool
    confidence: float
    strategy_name: str
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """验证决策数据的有效性"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"置信度必须在 0.0-1.0 之间，当前值: {self.confidence}")


class RouteStrategy(ABC):
    """路由策略抽象基类"""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self._initialized = False

    @abstractmethod
    def should_route_to_rag(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> RouteDecision:
        """
        判断是否应该路由到RAG模式

        Args:
            query: 用户查询文本
            context: 可选的上下文信息

        Returns:
            RouteDecision: 路由决策结果
        """
        pass

    def initialize(self) -> None:
        """
        初始化策略（延迟初始化模式）
        子类可以重写此方法进行资源加载等操作
        """
        if not self._initialized:
            logger.debug(f"📝 初始化路由策略: {self.name}")
            self._do_initialize()
            self._initialized = True

    def _do_initialize(self) -> None:
        """子类可重写的实际初始化逻辑"""
        pass

    @property
    def is_initialized(self) -> bool:
        """检查策略是否已初始化"""
        return self._initialized

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值的便捷方法"""
        return self.config.get(key, default)


class FallbackRouteStrategy(RouteStrategy):
    """回退路由策略 - 当所有其他策略失败时使用"""

    def __init__(self, default_to_rag: bool = False):
        super().__init__("fallback")
        self.default_to_rag = default_to_rag

    def should_route_to_rag(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> RouteDecision:
        """总是返回预设的默认决策"""
        return RouteDecision(
            should_use_rag=self.default_to_rag,
            confidence=0.1,  # 低置信度表示这是回退决策
            strategy_name=self.name,
            metadata={
                "reason": "fallback_strategy",
                "default_to_rag": self.default_to_rag,
            },
        )
