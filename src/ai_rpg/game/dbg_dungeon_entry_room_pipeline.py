"""副本入口场景流程管道工厂模块。"""

from typing import cast

from .base_game import BaseGame
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_dungeon_entry_room_pipeline(
    game: BaseGame,
) -> RPGGameProcessPipeline:
    """创建副本入口场景的流程管道（叙事 + 牌库生成，无战斗）"""

    ### 不这样就循环引用
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.appearance_initialization_system import (
        AppearanceInitializationSystem,
    )
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.entry_init_actor_system import EntryInitActorSystem
    from ..systems.epilogue_system import EpilogueSystem

    # from ..systems.generate_deck_action_system import GenerateDeckActionSystem
    from ..systems.prologue_system import PrologueSystem
    from ..systems.stage_description_system import (
        StageDescriptionSystem,
    )
    from .dbg_game import DBGGame

    dbg_game = cast(DBGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统
    processors.add(PrologueSystem(dbg_game))

    # 角色外观生成系统
    processors.add(AppearanceInitializationSystem(dbg_game))

    # 入口场景描述系统
    processors.add(StageDescriptionSystem(dbg_game))

    # 入口初始化系统（角色侧）：为入口场景内的远征队成员注入场景环境信息 + 为副本全部角色添加 GenerateDeckAction
    processors.add(EntryInitActorSystem(dbg_game))

    # 牌库生成系统：LLM 生成初始卡牌 → DeckComponent + DrawPileComponent
    # （临时停用：改用 Actor.cards 预置牌库）
    # processors.add(GenerateDeckActionSystem(dbg_game))

    # 清除动作相关的临时状态
    processors.add(ActionCleanupSystem(dbg_game))

    # 是否需要销毁实体
    processors.add(DestroyEntitySystem(dbg_game))

    # 收尾系统
    processors.add(EpilogueSystem(dbg_game))

    return processors
