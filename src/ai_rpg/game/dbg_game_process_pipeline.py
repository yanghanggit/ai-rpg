"""DBG游戏流程管道工厂模块，提供不同游戏场景的流程管道创建函数"""

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
    from ..systems.update_appearance_action_system import UpdateAppearanceActionSystem
    from ..systems.player_action_audit_system import PlayerActionAuditSystem
    from ..systems.stage_description_system import (
        StageDescriptionSystem,
    )
    from ..systems.home_npc_plan_system import HomeNpcPlanSystem
    from ..systems.home_player_plan_system import HomePlayerPlanSystem
    from ..systems.craft_consumable_action_system import CraftConsumableActionSystem
    from ..systems.craft_gear_item_action_system import CraftGearItemActionSystem
    from ..systems.craft_costume_item_action_system import CraftCostumeItemActionSystem

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
    processors.add(UpdateAppearanceActionSystem(dbg_game))

    # 制作相关的系统
    processors.add(CraftConsumableActionSystem(dbg_game))
    processors.add(CraftGearItemActionSystem(dbg_game))
    processors.add(CraftCostumeItemActionSystem(dbg_game))

    # 清除动作相关的临时状态、标记等，准备下一轮输入
    processors.add(ActionCleanupSystem(dbg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(dbg_game))

    # 收尾系统。
    processors.add(EpilogueSystem(dbg_game))

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
    from .dbg_game import DBGGame
    from ..systems.combat_outcome_system import CombatOutcomeSystem
    from ..systems.combat_initialization_system import (
        CombatInitializationSystem,
    )

    from ..systems.appearance_initialization_system import (
        AppearanceInitializationSystem,
    )
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.draw_cards_action_system import (
        DrawCardsActionSystem,
    )
    from ..systems.play_cards_action_system import (
        PlayCardsActionSystem,
    )
    from ..systems.use_consumable_item_action_system import (
        UseConsumableItemActionSystem,
    )
    from ..systems.use_gear_item_action_system import (
        UseGearItemActionSystem,
    )

    from ..systems.exhaust_cards_action_system import ExhaustCardsActionSystem
    from ..systems.move_to_discard_pile_system import MoveToDiscardPileSystem
    from ..systems.pass_turn_action_system import PassTurnActionSystem
    from ..systems.retreat_action_system import RetreatActionSystem
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.prologue_system import PrologueSystem

    from ..systems.play_cards_arbitration_system import PlayCardsArbitrationSystem
    from ..systems.use_consumable_item_arbitration_system import (
        UseConsumableItemArbitrationSystem,
    )
    from ..systems.use_gear_item_arbitration_system import (
        UseGearItemArbitrationSystem,
    )
    from ..systems.add_status_effects_action_system import (
        AddStatusEffectsActionSystem,
    )
    from ..systems.post_arbitration_action_system import (
        PostArbitrationActionSystem,
        CardInjectStrategy,
    )
    from ..systems.combat_archive_system import CombatArchiveSystem
    from ..systems.combat_loot_system import CombatLootSystem
    from ..systems.deck_generation_system import DeckGenerationSystem
    from ..systems.combat_pile_teardown_system import CombatPileTeardownSystem
    from ..systems.stage_description_system import (
        StageDescriptionSystem,
    )
    from ..systems.combat_round_cleanup_system import CombatRoundCleanupSystem
    from ..systems.combat_round_transition_system import (
        CombatRoundTransitionSystem,
        ActionOrderStrategy,
    )
    from ..systems.combat_round_completion_system import CombatRoundCompletionSystem
    from ..systems.monster_pre_play_system import MonsterPrePlaySystem
    from ..systems.party_pre_play_system import PartyPrePlaySystem

    dbg_game = cast(DBGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统。
    processors.add(PrologueSystem(dbg_game))

    # 角色外观生成系统
    processors.add(AppearanceInitializationSystem(dbg_game))

    # 战斗场景描述系统
    processors.add(StageDescriptionSystem(game=dbg_game))

    # 战斗初始化系统（注入战场上下文、转换战斗状态为进行中、触发初始状态效果
    processors.add(CombatInitializationSystem(dbg_game))

    # 牌库生成系统（战斗开始时为每个角色生成初始牌库
    processors.add(DeckGenerationSystem(dbg_game))

    # 战斗核心动作处理相关的系统
    processors.add(DrawCardsActionSystem(dbg_game))
    processors.add(MonsterPrePlaySystem(dbg_game))
    processors.add(PartyPrePlaySystem(dbg_game))
    processors.add(PlayCardsActionSystem(dbg_game))
    processors.add(UseConsumableItemActionSystem(dbg_game))
    processors.add(UseGearItemActionSystem(dbg_game))
    processors.add(MoveToDiscardPileSystem(dbg_game))
    processors.add(ExhaustCardsActionSystem(dbg_game))
    processors.add(PassTurnActionSystem(dbg_game))
    processors.add(RetreatActionSystem(dbg_game))
    processors.add(PlayCardsArbitrationSystem(dbg_game))
    processors.add(UseConsumableItemArbitrationSystem(dbg_game))
    processors.add(UseGearItemArbitrationSystem(dbg_game))
    processors.add(AddStatusEffectsActionSystem(dbg_game))

    # 仲裁结算后，由 stage agent（地牢主视角）决定是否对场内角色追加状态效果或塞牌
    processors.add(
        PostArbitrationActionSystem(dbg_game, strategy=CardInjectStrategy.RANDOM_INSERT)
    )

    # 回合完成判定系统
    processors.add(CombatRoundCompletionSystem(dbg_game))

    # 检查战斗结果系统
    processors.add(CombatOutcomeSystem(dbg_game))

    # 战斗回合清理系统（清除旧回合手牌 + 递减状态效果）
    processors.add(CombatRoundCleanupSystem(dbg_game))

    # 战斗回合过渡系统（创建新回合 + 生成 action_order）
    processors.add(
        CombatRoundTransitionSystem(dbg_game, strategy=ActionOrderStrategy.SPEED_ORDER)
    )

    # 战斗掉落系统（胜利时为每头怪物推理掉落 MaterialItem，写入玩家 CombatLootComponent）
    processors.add(CombatLootSystem(dbg_game))

    # 战斗归档系统（生成总结、压缩消息、触发记忆存储，内部有状态守卫）
    processors.add(CombatArchiveSystem(dbg_game))

    # 牌库归还系统（战斗结束后将三个子堆自有牌归还 DeckComponent）
    processors.add(CombatPileTeardownSystem(dbg_game))

    # 通用性的系统，用于后处理部分：清除动作相关的临时状态、标记等，准备下一轮输入
    processors.add(ActionCleanupSystem(dbg_game))

    # 是否需要销毁实体
    processors.add(DestroyEntitySystem(dbg_game))

    # 收尾系统。
    processors.add(EpilogueSystem(dbg_game))

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
    from .dbg_game import DBGGame
    from ..systems.generate_dungeon_ecology_system import GenerateDungeonEcologySystem
    from ..systems.generate_dungeon_stages_system import GenerateDungeonStagesSystem
    from ..systems.generate_dungeon_actors_system import GenerateDungeonActorsSystem
    from ..systems.assemble_dungeon_system import AssembleDungeonSystem

    # from ..systems.illustrate_dungeon_action_system import IllustrateDungeonActionSystem
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.prologue_system import PrologueSystem
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.destroy_entity_system import DestroyEntitySystem

    dbg_game = cast(DBGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统
    processors.add(PrologueSystem(dbg_game))

    # 地下城生成流程（Steps 1-4，在同一次 pipeline.process() 内顺序触发）
    processors.add(GenerateDungeonEcologySystem(dbg_game))  # Step 1: 生态环境生成
    processors.add(GenerateDungeonStagesSystem(dbg_game))  # Step 2: 场景批量生成
    processors.add(GenerateDungeonActorsSystem(dbg_game))  # Step 3: 怪物并发生成
    processors.add(AssembleDungeonSystem(dbg_game))  # Step 4: 实体树组装

    # 地下城图片生成系统（Step 5）
    # processors.add(IllustrateDungeonActionSystem(dbg_game))

    # 清除动作相关的临时状态、标记等，准备下一轮输入
    processors.add(ActionCleanupSystem(dbg_game))

    # 动作处理后，可能清理。
    processors.add(DestroyEntitySystem(dbg_game))

    # 收尾系统
    processors.add(EpilogueSystem(dbg_game))

    return processors
