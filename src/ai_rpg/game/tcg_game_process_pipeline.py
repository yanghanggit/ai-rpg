"""TCG游戏流程管道工厂模块，提供不同游戏场景的流程管道创建函数"""

from typing import cast
from .game_session import GameSession
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_home_pipeline(game: GameSession) -> "RPGGameProcessPipeline":
    """创建家园场景的流程管道（NPC 与玩家共用）

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
    from ..systems.player_action_audit_system import PlayerActionAuditSystem
    from ..systems.stage_description_system import (
        StageDescriptionSystem,
    )
    from ..systems.home_actor_system import HomeActorSystem

    ##
    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统。
    processors.add(PrologueSystem(tcg_game))

    # 角色外观生成系统
    processors.add(ActorAppearanceUpdateSystem(tcg_game))

    # 规划系统-场景描述系统-角色系统
    processors.add(StageDescriptionSystem(game=tcg_game, enable_debug_cache=True))
    processors.add(HomeActorSystem(tcg_game))

    # 动作处理相关的系统：查询-审核-说话-耳语-公告-场景转换-清理
    processors.add(QueryActionSystem(tcg_game))
    processors.add(PlayerActionAuditSystem(tcg_game))
    processors.add(SpeakActionSystem(tcg_game))
    processors.add(WhisperActionSystem(tcg_game))
    processors.add(AnnounceActionSystem(tcg_game))
    processors.add(TransStageActionSystem(tcg_game))

    # 清除动作相关的临时状态、标记等，准备下一轮输入
    processors.add(ActionCleanupSystem(tcg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 收尾系统。
    processors.add(EpilogueSystem(tcg_game))

    return processors


def create_combat_pipeline(
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

    # from ..systems.enemy_draw_decision_system import (
    #     EnemyDrawDecisionSystem,
    # )
    from ..systems.draw_cards_action_system import (
        DrawCardsActionSystem,
    )

    from ..systems.play_cards_action_system import (
        PlayCardsActionSystem,
    )
    from ..systems.retreat_action_system import RetreatActionSystem
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.prologue_system import PrologueSystem

    from ..systems.arbitration_action_system import ArbitrationActionSystem
    from ..systems.add_status_effects_action_system import (
        AddStatusEffectsActionSystem,
    )
    from ..systems.combat_archive_system import CombatArchiveSystem
    from ..systems.stage_description_system import (
        StageDescriptionSystem,
    )
    from ..systems.combat_round_creation_system import CombatRoundCreationSystem

    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统。
    processors.add(PrologueSystem(tcg_game))

    # 角色外观生成系统
    processors.add(ActorAppearanceUpdateSystem(tcg_game))

    # 战斗场景描述系统（与家园共用，内部有状态守卫，只有在战斗开始时才会触发）
    processors.add(StageDescriptionSystem(game=tcg_game, enable_debug_cache=True))

    # 战斗初始化系统（创建第一回合）
    processors.add(CombatInitializationSystem(tcg_game))

    # 战斗回合创建系统（创建后续回合）
    processors.add(CombatRoundCreationSystem(tcg_game))

    # 动作处理相关的系统：敌人决策-抓牌-出牌-撤退-裁决-清理
    # processors.add(EnemyDrawDecisionSystem(tcg_game))
    processors.add(DrawCardsActionSystem(tcg_game, 3))
    processors.add(PlayCardsActionSystem(tcg_game))
    processors.add(RetreatActionSystem(tcg_game))
    processors.add(ArbitrationActionSystem(tcg_game))

    # 检查战斗结果系统
    processors.add(CombatOutcomeSystem(tcg_game))

    # 状态效果追加系统（AI 根据回合结算结果追加新状态效果，内部有状态守卫）
    processors.add(AddStatusEffectsActionSystem(tcg_game))

    # 战斗归档系统（生成总结、压缩消息、触发记忆存储，内部有状态守卫）
    processors.add(CombatArchiveSystem(tcg_game))

    # 清除动作相关的临时状态、标记等，准备下一轮输入
    processors.add(ActionCleanupSystem(tcg_game))

    # 是否需要销毁实体
    processors.add(DestroyEntitySystem(tcg_game))

    # 收尾系统。
    processors.add(EpilogueSystem(tcg_game))

    return processors


def create_dungeon_generate_pipeline(
    game: GameSession,
) -> "RPGGameProcessPipeline":
    """创建地下城生成流程管道（LLM 文本生成 + 图片生成）

    由 GenerateDungeonAction / IllustrateDungeonAction 驱动，负责调用 LLM 生成
    地下城文本数据（Steps 1-4）并生成对应图片（Step 5），输出结果为 JSON/图片文件。
    不涉及运行时 Entity 实例化（那是 setup_dungeon 的职责）。

    Args:
        game: 游戏会话实例

    Returns:
        配置好的RPG游戏流程管道实例
    """

    ### 不这样就循环引用
    from ..game.tcg_game import TCGGame
    from ..systems.generate_dungeon_action_system import GenerateDungeonActionSystem
    from ..systems.illustrate_dungeon_action_system import IllustrateDungeonActionSystem
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.prologue_system import PrologueSystem
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem

    tcg_game = cast(TCGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统
    processors.add(PrologueSystem(tcg_game))

    # 地下城文本数据生成系统（Steps 1-4）
    processors.add(GenerateDungeonActionSystem(tcg_game))

    # 地下城图片生成系统（Step 5）
    processors.add(IllustrateDungeonActionSystem(tcg_game))

    # 清除动作相关的临时状态、标记等，准备下一轮输入
    processors.add(ActionCleanupSystem(tcg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(tcg_game))

    # 收尾系统
    processors.add(EpilogueSystem(tcg_game))

    return processors
