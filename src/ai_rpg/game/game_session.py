"""
AI-RPG 游戏框架基础类模块

定义游戏框架的基础抽象类，为所有游戏类型提供统一的接口和基础功能。
"""

from abc import ABC, abstractmethod
from typing import Final


class GameSession(ABC):
    """
    游戏框架基础抽象类

    所有游戏类型的基类，定义游戏的基本属性和生命周期方法。
    """

    def __init__(self, name: str) -> None:
        """
        初始化游戏基础属性

        Args:
            name: 游戏实例名称
        """
        self._name: Final[str] = name  # 游戏名称，创建后不可修改
        self._should_terminate: bool = False  # 终止标志，用于优雅退出控制

    # ═══════════════════════════════════════════════════════════════════════
    # 属性访问器 - 游戏基础信息
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def name(self) -> str:
        """
        获取游戏名称

        Returns:
            str: 游戏实例名称
        """
        return self._name

    # ═══════════════════════════════════════════════════════════════════════
    # 属性访问器 - 游戏状态控制
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def should_terminate(self) -> bool:
        """
        检查游戏是否应该终止

        Returns:
            bool: True 表示游戏应该终止
        """
        return self._should_terminate

    @should_terminate.setter
    def should_terminate(self, value: bool) -> None:
        """
        设置游戏终止标志

        Args:
            value: True 表示请求终止游戏
        """
        self._should_terminate = value

    # ═══════════════════════════════════════════════════════════════════════
    # 抽象方法 - 子类必须实现的生命周期方法
    # ═══════════════════════════════════════════════════════════════════════

    @abstractmethod
    async def initialize(self) -> None:
        """
        异步初始化游戏

        子类必须实现此方法来完成游戏的初始化工作。
        """
        pass

    @abstractmethod
    def exit(self) -> None:
        """
        同步退出游戏

        子类必须实现此方法来完成游戏的清理和退出工作。
        """
        pass
