"""TCG游戏流程管道工厂模块，提供不同游戏场景的流程管道创建函数"""

from typing import cast
from .game_session import GameSession
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_npc_home_pipeline(game: GameSession) -> "RPGGameProcessPipeline":
    """创建NPC家园场景的流程管道

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

    # from ..systems.home_auto_plan_system import HomeAutoPlanSystem
    from ..systems.home_stage_description_system import (
        HomeStageDescriptionSystem,
    )
    from ..systems.home_actor_system import HomeActorSystem

    ##
    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline()

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 角色外观生成系统
    processors.add(ActorAppearanceUpdateSystem(tcg_game))

    # 规划系统-场景描述系统-角色系统
    # processors.add(HomeAutoPlanSystem(tcg_game))
    processors.add(HomeStageDescriptionSystem(tcg_game))
    processors.add(HomeActorSystem(tcg_game))

    # 动作处理相关的系统：查询-说话-耳语-公告-场景转换-清理
    processors.add(QueryActionSystem(tcg_game))
    processors.add(SpeakActionSystem(tcg_game))
    processors.add(WhisperActionSystem(tcg_game))
    processors.add(AnnounceActionSystem(tcg_game))
    processors.add(TransStageActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


def create_player_home_pipeline(game: GameSession) -> "RPGGameProcessPipeline":
    """创建玩家家园场景的流程管道

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

    ##
    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline()

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 角色外观生成系统
    processors.add(ActorAppearanceUpdateSystem(tcg_game))

    # 动作处理相关的系统：说话-耳语-公告-场景转换-清理
    # processors.add(PlayerActionAuditSystem(tcg_game))
    processors.add(SpeakActionSystem(tcg_game))
    processors.add(WhisperActionSystem(tcg_game))
    processors.add(AnnounceActionSystem(tcg_game))
    processors.add(TransStageActionSystem(tcg_game))
    processors.add(ActionCleanupSystem(tcg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


def create_combat_execution_pipeline(
    game: GameSession,
) -> "RPGGameProcessPipeline":
    """创建地牢战斗场景的流程管道

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
    from ..systems.combat_round_creation_system import (
        CombatRoundCreationSystem,
    )
    from ..systems.enemy_draw_decision_system import (
        EnemyDrawDecisionSystem,
    )
    from ..systems.draw_cards_action_system import (
        DrawCardsActionSystem,
    )
    from ..systems.play_cards_action_system import (
        PlayCardsActionSystem,
    )
    from ..systems.kick_off_system import KickOffSystem
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.save_system import SaveSystem
    from ..systems.arbitration_action_system import ArbitrationActionSystem

    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline()

    # 启动agent的提示词。启动阶段
    processors.add(KickOffSystem(tcg_game, True))

    # 角色外观生成系统
    processors.add(ActorAppearanceUpdateSystem(tcg_game))

    # 战斗初始化系统（创建第一回合）
    processors.add(CombatInitializationSystem(tcg_game))

    # 战斗回合创建系统（创建后续回合）
    processors.add(CombatRoundCreationSystem(tcg_game))

    # 动作处理相关的系统：敌人决策-抓牌-出牌-裁决-清理
    processors.add(EnemyDrawDecisionSystem(tcg_game))
    processors.add(DrawCardsActionSystem(tcg_game))
    processors.add(PlayCardsActionSystem(tcg_game))
    processors.add(ArbitrationActionSystem(tcg_game))

    processors.add(ActionCleanupSystem(tcg_game))

    # 检查战斗结果系统
    processors.add(CombatOutcomeSystem(tcg_game))

    # 是否需要销毁实体
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


def create_combat_archive_pipeline(
    game: GameSession,
) -> "RPGGameProcessPipeline":
    """创建战斗归档流程管道

    用于战斗结束后的记录归档处理：
    - 生成战斗总结：通过AI为每个角色生成第一人称战斗记录
    - 压缩历史消息：提取并删除战斗期间的详细消息，节省上下文空间
    - 归档记忆：将战斗经历存入知识库

    Args:
        game: 游戏会话实例

    Returns:
        配置好的RPG游戏流程管道实例

    Note:
        此pipeline应在战斗完成后（is_completed=True）调用，
        且战斗结果必须为胜利或失败状态
    """

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..systems.combat_archive_system import CombatArchiveSystem
    from ..systems.save_system import SaveSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem

    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline()

    # 战斗归档系统（生成总结、压缩消息、触发记忆存储）
    processors.add(CombatArchiveSystem(tcg_game))

    # 是否需要销毁实体
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors


def create_combat_status_evaluation_pipeline(
    game: GameSession,
) -> "RPGGameProcessPipeline":
    """创建战斗状态效果评估流程管道

    用于战斗回合后的状态效果评估：
    - 为每个存活角色评估战斗后的状态效果
    - 根据战斗演出和数据日志生成新的状态效果
    - 自动添加到角色的状态效果列表

    Args:
        game: 游戏会话实例

    Returns:
        配置好的RPG游戏流程管道实例

    Note:
        此pipeline应在战斗裁决后（ArbitrationActionSystem）手动调用，
        用于按需触发状态效果评估，而非每回合自动执行
    """

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..systems.status_effects_evaluation_system import (
        StatusEffectsEvaluationSystem,
    )
    from ..systems.save_system import SaveSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem

    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline()

    # 状态效果评估系统（AI 生成新的状态效果）
    processors.add(StatusEffectsEvaluationSystem(tcg_game))

    # 是否需要销毁实体
    processors.add(DestroyEntitySystem(tcg_game))

    # 存储系统。
    processors.add(SaveSystem(tcg_game))

    return processors
