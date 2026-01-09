"""
TCG游戏流程管道工厂模块

本模块提供不同游戏场景的流程管道创建工厂函数，用于构建和配置各种游戏场景下的系统处理流程。

主要功能：
- 创建NPC家园场景流程管道：包含NPC自动规划、行为决策和社交互动系统
- 创建玩家家园场景流程管道：处理玩家的社交互动和场景切换
- 创建地牢战斗场景流程管道：完整的卡牌战斗流程，包括抽卡、出牌、裁决和战斗结算

使用方式：
    pipeline = create_npc_home_pipeline(game_session)
    await pipeline.process()
"""

from typing import cast
from .game_session import GameSession
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_npc_home_pipeline(game: GameSession) -> "RPGGameProcessPipeline":
    """
    创建NPC家园场景的流程管道

    构建NPC在家园场景中的完整游戏流程，包括自动规划、行为决策、
    动作执行（查询、说话、耳语、公告、场景切换）以及实体清理和存储。

    Args:
        game: 游戏会话实例

    Returns:
        配置好的RPG游戏流程管道实例
    """

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..systems.announce_action_system import AnnounceActionSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.actor_appearance_update_system import (
        ActorAppearanceUpdateSystem,
    )
    from ..systems.kick_off_system import KickOffSystem
    from ..systems.query_action_system import (
        QueryActionSystem,
    )
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.save_system import SaveSystem
    from ..systems.speak_action_system import SpeakActionSystem
    from ..systems.whisper_action_system import WhisperActionSystem
    from ..systems.trans_stage_action_system import (
        TransStageActionSystem,
    )

    ##
    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline()

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 角色外观生成系统
    processors.add(ActorAppearanceUpdateSystem(tcg_game))

    # 规划逻辑
    ######## 在所有规划之前!##############################################################
    # processors.add(HomeAutoPlanSystem(tcg_game))
    # processors.add(HomeStageDescriptionSystem(tcg_game))
    # processors.add(HomeActorSystem(tcg_game))
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


def create_player_home_pipeline(game: GameSession) -> "RPGGameProcessPipeline":
    """
    创建玩家家园场景的流程管道

    构建玩家在家园场景中的游戏流程，处理玩家的社交互动行为
    （说话、耳语、公告）、场景切换以及实体清理和存储。

    Args:
        game: 游戏会话实例

    Returns:
        配置好的RPG游戏流程管道实例
    """

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..systems.announce_action_system import AnnounceActionSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.actor_appearance_update_system import (
        ActorAppearanceUpdateSystem,
    )
    from ..systems.kick_off_system import KickOffSystem
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.save_system import SaveSystem
    from ..systems.speak_action_system import SpeakActionSystem
    from ..systems.whisper_action_system import WhisperActionSystem
    from ..systems.trans_stage_action_system import (
        TransStageActionSystem,
    )

    # from ..systems.player_action_audit_system import PlayerActionAuditSystem

    ##
    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline()

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 角色外观生成系统
    processors.add(ActorAppearanceUpdateSystem(tcg_game))

    # 动作处理相关的系统 ##################################################################
    ####################################################################################
    # processors.add(PlayerActionAuditSystem(tcg_game))
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


def create_dungeon_combat_pipeline(
    game: GameSession,
) -> "RPGGameProcessPipeline":
    """
    创建地牢战斗场景的流程管道

    构建地牢战斗的完整流程管道，包括战斗初始化、状态效果结算、
    唯一道具通知、抽卡出牌、裁决、战斗结果判定以及战后处理。

    执行顺序：
    1. 战斗初始化
    2. 状态效果结算（必须在抽卡前）
    3. 唯一道具通知
    4. 抽卡和出牌动作
    5. 战斗裁决
    6. 战斗结果判定和后处理
    7. 实体清理和存储

    Args:
        game: 游戏会话实例

    Returns:
        配置好的RPG游戏流程管道实例
    """

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..systems.combat_outcome_system import CombatOutcomeSystem
    from ..systems.combat_initialization_system import (
        CombatInitializationSystem,
    )
    from ..systems.actor_appearance_update_system import (
        ActorAppearanceUpdateSystem,
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
    processors = RPGGameProcessPipeline()

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 角色外观生成系统
    processors.add(ActorAppearanceUpdateSystem(tcg_game))

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
