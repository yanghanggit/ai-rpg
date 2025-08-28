"""Multi-Agent Game Framework

A framework for building multi-agent games using ECS architecture.
"""

__version__ = "0.1.0"
__author__ = "Yang Hang"

# 导出主要类和函数
try:
    from .chat_services.manager import ChatClientManager
    from .entitas import Context, Entity
    from .game.base_game import BaseGame
    from .game.tcg_game import TCGGame
    from .models.dungeon import Dungeon
    from .models.objects import Actor, Stage

    __all__ = [
        "BaseGame",
        "TCGGame",
        "Actor",
        "Stage",
        "Dungeon",
        "ChatClientManager",
        "Context",
        "Entity",
    ]
except ImportError:
    # 在包构建过程中可能会出现导入错误，这是正常的
    __all__ = []
