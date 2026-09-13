"""副本开场场景流程管道工厂模块。"""

from typing import cast

from .base_game import BaseGame
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_dungeon_opening_room_pipeline(
    game: BaseGame,
) -> RPGGameProcessPipeline:
    """创建副本开场场景的流程管道（叙事 + 牌库初始化，无战斗；卡池生成由外部显式触发 GenerateCardPoolAction）"""

    ### 不这样就循环引用
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.appearance_initialization_system import (
        AppearanceInitializationSystem,
    )
    from ..systems.artifact_initialization_system import ArtifactInitializationSystem
    from ..systems.context_compaction_system import ContextCompactionSystem
    from ..systems.deck_initialization_system import DeckInitializationSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.environment_initialization_system import (
        EnvironmentInitializationSystem,
    )
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.generate_card_pool_action_system import (
        GenerateCardPoolActionSystem,
    )
    from ..systems.opening_init_actor_system import OpeningInitActorSystem
    from ..systems.pick_card_action_system import (
        PickCardActionSystem,
    )
    from ..systems.prologue_system import PrologueSystem
    from .dbg_game import DBGGame

    dbg_game = cast(DBGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统
    processors.add(PrologueSystem(dbg_game))

    # 角色外观生成系统
    processors.add(AppearanceInitializationSystem(dbg_game))

    # 开场环境初始化系统
    processors.add(EnvironmentInitializationSystem(dbg_game))

    # 神器实体初始化系统：将持有者 ReliquaryComponent 声明的神器物化为神器实体（幂等）
    processors.add(ArtifactInitializationSystem(dbg_game))

    # 开场初始化系统（角色侧）：为开场场景内的队伍成员注入场景环境信息
    processors.add(OpeningInitActorSystem(dbg_game))

    # 牌库初始化系统：回填空 source 卡牌并做叙事个人化（幂等）
    processors.add(DeckInitializationSystem(dbg_game))

    # 卡池系统：从原型库抽取候选卡并润色后装入卡池（响应 GenerateCardPoolAction）
    processors.add(GenerateCardPoolActionSystem(dbg_game))

    # 从卡池挑选卡牌系统：选中卡加入牌库并清空卡池（响应 PickCardFromPoolAction）
    processors.add(PickCardActionSystem(dbg_game))

    # 清除动作相关的临时状态
    processors.add(ActionCleanupSystem(dbg_game))

    # 是否需要销毁实体
    processors.add(DestroyEntitySystem(dbg_game))

    # 上下文压缩系统：上下文占比超阈值时压缩记忆
    processors.add(ContextCompactionSystem(dbg_game))

    # 收尾系统
    processors.add(EpilogueSystem(dbg_game))

    return processors
