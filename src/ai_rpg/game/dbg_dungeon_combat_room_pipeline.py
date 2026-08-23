"""地牢战斗场景流程管道工厂模块。"""

from typing import cast
from .game_session import GameSession
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_dungeon_combat_room_pipeline(
    game: GameSession,
) -> RPGGameProcessPipeline:
    """创建地牢战斗场景的流程管道"""

    ### 不这样就循环引用
    from .dbg_game import DBGGame
    from ..systems.combat_outcome_system import CombatOutcomeSystem
    from ..systems.combat_init_actor_system import CombatInitActorSystem
    from ..systems.combat_init_stage_system import CombatInitStageSystem

    from ..systems.appearance_initialization_system import (
        AppearanceInitializationSystem,
    )
    from ..systems.destroy_entity_system import DestroyEntitySystem
    from ..systems.draw_cards_action_system import (
        DrawCardsActionSystem,
    )
    from ..systems.post_draw_cards_system import (
        PostDrawCardsSystem,
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
    from ..systems.inject_cards_action_system import (
        InjectCardsActionSystem,
    )
    from ..systems.combat_archive_system import CombatArchiveSystem
    from ..systems.combat_loot_system import CombatLootSystem
    from ..systems.fill_draw_pile_system import FillDrawPileSystem
    from ..systems.combat_pile_teardown_system import CombatPileTeardownSystem
    from ..systems.stage_description_system import (
        StageDescriptionSystem,
    )
    from ..systems.combat_round_cleanup_system import CombatRoundCleanupSystem
    from ..systems.combat_round_end_settlement_system import (
        CombatRoundEndSettlementSystem,
    )
    from ..systems.death_system import DeathSystem
    from ..systems.combat_status_effect_tick_system import CombatStatusEffectTickSystem
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
    processors.add(StageDescriptionSystem(dbg_game))

    # 战斗初始化系统（角色侧）：初始化战斗临时牌堆/状态效果组件，为参战角色注入战场上下文，触发初始牌库生成
    processors.add(CombatInitActorSystem(dbg_game))

    # 战斗初始化系统（场景侧）：注入战斗专用规则、转换战斗状态为进行中、推理场景状态效果依据
    processors.add(CombatInitStageSystem(dbg_game))

    # 抽牌堆填充系统（从 DeckComponent 填 DrawPileComponent，零 LLM）
    processors.add(FillDrawPileSystem(dbg_game))

    # 战斗核心动作处理相关的系统
    processors.add(DrawCardsActionSystem(dbg_game))
    processors.add(PostDrawCardsSystem(dbg_game))
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
    processors.add(DeathSystem(dbg_game))

    # 仂裁结算后，由 stage agent（地牢主视角）复用已更新的对话上下文，判断是否需要向场内角色塞入场景卡牌
    processors.add(InjectCardsActionSystem(dbg_game))

    # 回合完成判定系统
    processors.add(CombatRoundCompletionSystem(dbg_game))

    # 战斗回合清理系统（清除旧回合手牌状态）
    processors.add(CombatRoundCleanupSystem(dbg_game))

    # 战斗回合末状态效果结算系统（并发 LLM 推理 ROUND_END 效果 HP 变化）
    processors.add(CombatRoundEndSettlementSystem(dbg_game))

    # 死亡处理系统（ROUND_END 效果结算后标记 HP 归零的实体）
    processors.add(DeathSystem(dbg_game))

    # 状态效果追加系统（统一在回合末结算与死亡标记之后落地：
    # 仲裁阶段 + 回合末繁殖的 AddStatusEffectsAction 均在此处理，同名覆盖/异名追加）
    processors.add(AddStatusEffectsActionSystem(dbg_game))

    # 检查战斗结果系统（必须在死亡标记之后，才能在同一周期内根据最终存活情况判定胜负）
    processors.add(CombatOutcomeSystem(dbg_game))

    # 战斗状态效果 tick 系统（推进持续时间、移除到期效果）
    processors.add(CombatStatusEffectTickSystem(dbg_game))

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
