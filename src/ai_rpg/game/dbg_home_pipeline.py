"""家园场景流程管道工厂模块。"""

from typing import cast
from .game_session import GameSession
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_home_pipeline(game: GameSession) -> RPGGameProcessPipeline:
    """创建家园场景的流程管道（NPC 与玩家共用）"""

    ### 不这样就循环引用
    from .dbg_game import DBGGame
    from ..systems.announce_action_system import AnnounceActionSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem

    from ..systems.appearance_initialization_system import (
        AppearanceInitializationSystem,
    )
    from ..systems.query_action_system import (
        QueryActionSystem,
    )
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.prologue_system import PrologueSystem
    from ..systems.speak_action_system import SpeakActionSystem
    from ..systems.whisper_action_system import WhisperActionSystem
    from ..systems.trans_stage_action_system import (
        TransStageActionSystem,
    )
    from ..systems.wear_costume_action_system import WearCostumeActionSystem
    from ..systems.remove_costume_action_system import RemoveCostumeActionSystem
    from ..systems.player_action_audit_system import PlayerActionAuditSystem
    from ..systems.stage_description_system import (
        StageDescriptionSystem,
    )
    from ..systems.home_npc_plan_system import HomeNpcPlanSystem
    from ..systems.home_player_plan_system import HomePlayerPlanSystem

    ##
    dbg_game = cast(DBGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统。
    processors.add(PrologueSystem(dbg_game))

    # 角色外观生成系统
    processors.add(AppearanceInitializationSystem(dbg_game))

    # 规划系统-场景描述系统-角色系统
    processors.add(StageDescriptionSystem(dbg_game))
    processors.add(HomePlayerPlanSystem(dbg_game))
    processors.add(HomeNpcPlanSystem(dbg_game))

    # 动作处理相关的系统
    processors.add(QueryActionSystem(dbg_game))
    processors.add(PlayerActionAuditSystem(dbg_game))
    processors.add(SpeakActionSystem(dbg_game))
    processors.add(WhisperActionSystem(dbg_game))
    processors.add(AnnounceActionSystem(dbg_game))
    processors.add(TransStageActionSystem(dbg_game))
    processors.add(RemoveCostumeActionSystem(dbg_game))
    processors.add(WearCostumeActionSystem(dbg_game))

    # 清除动作相关的临时状态、标记等，准备下一轮输入
    processors.add(ActionCleanupSystem(dbg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(dbg_game))

    # 收尾系统。
    processors.add(EpilogueSystem(dbg_game))

    return processors
