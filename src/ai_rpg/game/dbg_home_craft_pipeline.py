"""家园制作流程管道工厂模块（仅在玩家处于家园场景时使用）。"""

from typing import cast
from .base_game import BaseGame
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_home_craft_pipeline(game: BaseGame) -> RPGGameProcessPipeline:
    """创建家园制作流程管道（仅处理 craft 动作）"""

    ### 不这样就循环引用
    from .dbg_game import DBGGame
    from ..systems.destroy_entity_system import DestroyEntitySystem

    from ..systems.appearance_initialization_system import (
        AppearanceInitializationSystem,
    )
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.prologue_system import PrologueSystem
    from ..systems.stage_description_system import (
        StageDescriptionSystem,
    )
    from ..systems.craft_consumable_item_action_system import (
        CraftConsumableItemActionSystem,
    )
    from ..systems.craft_gear_item_action_system import CraftGearItemActionSystem
    from ..systems.craft_costume_item_action_system import CraftCostumeItemActionSystem

    ##
    dbg_game = cast(DBGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统。
    processors.add(PrologueSystem(dbg_game))

    # 角色外观生成系统
    processors.add(AppearanceInitializationSystem(dbg_game))

    # 场景描述系统
    processors.add(StageDescriptionSystem(dbg_game))

    # 制作相关的系统
    processors.add(CraftConsumableItemActionSystem(dbg_game))
    processors.add(CraftGearItemActionSystem(dbg_game))
    processors.add(CraftCostumeItemActionSystem(dbg_game))

    # 清除动作相关的临时状态、标记等，准备下一轮输入
    processors.add(ActionCleanupSystem(dbg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(dbg_game))

    # 收尾系统。
    processors.add(EpilogueSystem(dbg_game))

    return processors
