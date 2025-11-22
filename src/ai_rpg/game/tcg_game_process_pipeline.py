from typing import cast
from .game_session import GameSession
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_npc_home_pipline(game: GameSession) -> "RPGGameProcessPipeline":

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..systems.announce_action_system import AnnounceActionSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.home_actor_system import (
        HomeActorSystem,
    )
    from ..systems.home_stage_system import (
        HomeStageSystem,
    )
    from ..systems.kick_off_system import KickOffSystem
    from ..systems.query_action_system import (
        QueryActionSystem,
    )
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.save_system import SaveSystem
    from ..systems.speak_action_system import SpeakActionSystem
    from ..systems.whisper_action_system import WhisperActionSystem
    from ..systems.home_auto_plan_system import HomeAutoPlanSystem
    from ..systems.trans_stage_action_system import (
        TransStageActionSystem,
    )

    ##
    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline("Home State Pipeline 1")

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 规划逻辑
    ######## 在所有规划之前!##############################################################
    processors.add(HomeAutoPlanSystem(tcg_game))
    processors.add(HomeStageSystem(tcg_game))
    processors.add(HomeActorSystem(tcg_game))
    ####### 在所有规划之后! ##############################################################

    # 动作处理相关的系统 ##################################################################
    ####################################################################################
    processors.add(QueryActionSystem(tcg_game))
    processors.add(SpeakActionSystem(tcg_game))
    processors.add(WhisperActionSystem(tcg_game))
    processors.add(AnnounceActionSystem(tcg_game))
    processors.add(TransStageActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))
    ####################################################################################
    ####################################################################################

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


def create_player_home_pipline(game: GameSession) -> "RPGGameProcessPipeline":

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..systems.announce_action_system import AnnounceActionSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.kick_off_system import KickOffSystem
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.save_system import SaveSystem
    from ..systems.speak_action_system import SpeakActionSystem
    from ..systems.whisper_action_system import WhisperActionSystem
    from ..systems.trans_stage_action_system import (
        TransStageActionSystem,
    )

    ##
    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline("Home State Pipeline 2")

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 动作处理相关的系统 ##################################################################
    ####################################################################################
    processors.add(SpeakActionSystem(tcg_game))
    processors.add(WhisperActionSystem(tcg_game))
    processors.add(AnnounceActionSystem(tcg_game))
    processors.add(TransStageActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))
    ####################################################################################
    ####################################################################################

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


def create_dungeon_combat_state_pipeline(
    game: GameSession,
) -> "RPGGameProcessPipeline":

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..systems.combat_outcome_system import CombatOutcomeSystem
    from ..systems.combat_initialization_system import (
        CombatInitializationSystem,
    )
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.draw_cards_action_system import (
        DrawCardsActionSystem,
    )
    from ..systems.play_cards_action_system import (
        PlayCardsActionSystem,
    )
    from ..systems.combat_post_processing_system import (
        CombatPostProcessingSystem,
    )
    from ..systems.kick_off_system import KickOffSystem
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.save_system import SaveSystem
    from ..systems.arbitration_action_system import ArbitrationActionSystem
    from ..systems.status_effects_settlement_system import (
        StatusEffectsSettlementSystem,
    )
    from ..systems.unique_item_notification_system import (
        UniqueItemNotificationSystem,
    )

    ##
    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline("Dungeon Combat State Pipeline")

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))
    processors.add(CombatInitializationSystem(tcg_game))

    # 状态效果结算系统（必须在抽卡之前执行）
    processors.add(StatusEffectsSettlementSystem(tcg_game))

    # 唯一道具通知系统（在状态效果结算之后、抽卡之前执行）
    processors.add(UniqueItemNotificationSystem(tcg_game))

    # 抽卡。
    ######动作开始！！！！！################################################################################################
    processors.add(DrawCardsActionSystem(tcg_game))
    processors.add(PlayCardsActionSystem(tcg_game))
    processors.add(ArbitrationActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))
    ###### 动作结束！！！！！################################################################################################

    # 检查死亡
    processors.add(CombatOutcomeSystem(tcg_game))
    processors.add(CombatPostProcessingSystem(tcg_game))

    # 核心系统，检查需要删除的实体。
    processors.add(DestroyEntitySystem(tcg_game))

    # 核心系统，存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors
