"""上下文压缩流程管道工厂模块（与具体场景状态无关，仅处理 CompactContextAction）。"""

from typing import cast

from .base_game import BaseGame
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_compact_pipeline(game: BaseGame) -> RPGGameProcessPipeline:
    """创建上下文压缩流程管道（仅处理 CompactContextAction）"""

    ### 不这样就循环引用
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.compact_context_action_system import CompactContextActionSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.prologue_system import PrologueSystem
    from .dbg_game import DBGGame

    dbg_game = cast(DBGGame, game)
    processors = RPGGameProcessPipeline()

    # 前置系统：序章
    processors.add(PrologueSystem(dbg_game))

    # 手动压缩动作系统：响应 CompactContextAction，压缩指定实体的记忆
    processors.add(CompactContextActionSystem(dbg_game))

    # 清除动作相关的临时状态，防止动作跨帧残留
    processors.add(ActionCleanupSystem(dbg_game))

    # 销毁实体系统：处理需要被销毁的实体
    processors.add(DestroyEntitySystem(dbg_game))

    # 后置系统：尾声
    processors.add(EpilogueSystem(dbg_game))

    # 返回构建好的流程管道
    return processors
