"""地牢战斗场景流程管道工厂模块。"""

from typing import cast
from .base_game import BaseGame
from .rpg_game_pipeline_manager import RPGGameProcessPipeline


def create_dungeon_combat_room_pipeline(
    game: BaseGame,
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
    from ..systems.play_cards_action_system import (
        PlayCardsActionSystem,
    )
    from ..systems.transfer_cards_action_system import (
        TransferCardsActionSystem,
    )
    from ..systems.use_consumable_item_action_system import (
        UseConsumableItemActionSystem,
    )
    from ..systems.equip_gear_item_action_system import (
        EquipGearItemActionSystem,
    )

    from ..systems.exhaust_cards_action_system import ExhaustCardsActionSystem
    from ..systems.exhaust_ethereal_cards_system import ExhaustEtherealCardsSystem
    from ..systems.discard_cards_action_system import DiscardCardsActionSystem
    from ..systems.pass_turn_action_system import PassTurnActionSystem
    from ..systems.retreat_action_system import RetreatActionSystem
    from ..systems.action_cleanup_system import ActionCleanupSystem
    from ..systems.epilogue_system import EpilogueSystem
    from ..systems.prologue_system import PrologueSystem

    from ..systems.play_cards_arbitration_system import PlayCardsArbitrationSystem
    from ..systems.use_consumable_item_arbitration_system import (
        UseConsumableItemArbitrationSystem,
    )
    from ..systems.turn_end_arbitration_system import TurnEndArbitrationSystem
    from ..systems.combat_archive_system import CombatArchiveSystem
    from ..systems.combat_loot_system import CombatLootSystem
    from ..systems.fill_draw_pile_system import FillDrawPileSystem

    # from ..systems.generate_deck_action_system import GenerateDeckActionSystem
    from ..systems.combat_pile_teardown_system import CombatPileTeardownSystem
    from ..systems.stage_description_system import (
        StageDescriptionSystem,
    )
    from ..systems.combat_round_cleanup_system import CombatRoundCleanupSystem
    from ..systems.death_system import DeathSystem
    from ..systems.combat_round_transition_system import (
        CombatRoundTransitionSystem,
        ActionOrderStrategy,
    )
    from ..systems.combat_round_completion_system import CombatRoundCompletionSystem
    from ..systems.monster_pre_play_system import MonsterPrePlaySystem

    # from ..systems.monster_memory_probe_system import MonsterMemoryProbeSystem
    from ..systems.party_pre_play_system import PartyPrePlaySystem

    dbg_game = cast(DBGGame, game)
    processors = RPGGameProcessPipeline()

    # 起始系统。
    processors.add(PrologueSystem(dbg_game))

    # 角色外观生成系统
    processors.add(AppearanceInitializationSystem(dbg_game))

    # 战斗场景描述系统
    processors.add(StageDescriptionSystem(dbg_game))

    # 战斗初始化系统（角色侧）：初始化战斗临时牌堆，为参战角色注入战场环境，添加 GenerateDeckAction
    processors.add(CombatInitActorSystem(dbg_game))

    # 战斗初始化系统（场景侧）：注入战斗专用规则、转换战斗状态为进行中
    processors.add(CombatInitStageSystem(dbg_game))

    # 怪物牌库生成系统：响应 GenerateDeckAction，为当前战斗房间的怪物生成初始牌库；
    # 远征队牌库已在入口房间生成，此处因牌库非空被 filter 跳过
    # （临时停用：改用 Actor.cards 预置牌库）
    # processors.add(GenerateDeckActionSystem(dbg_game))

    # 抽牌堆填充系统（从 DeckComponent 填 DrawPileComponent，零 LLM）
    processors.add(FillDrawPileSystem(dbg_game))

    # 战斗核心动作处理相关的系统
    processors.add(DrawCardsActionSystem(dbg_game))
    # processors.add(
    #     MonsterMemoryProbeSystem(dbg_game)
    # )  # 纯调试系统：在怪物出牌决策前探测其记忆同步是否正确，问题/回答不写入 LLM 记忆。
    processors.add(MonsterPrePlaySystem(dbg_game))
    processors.add(PartyPrePlaySystem(dbg_game))

    # 撤退动作系统
    processors.add(RetreatActionSystem(dbg_game))

    # 战斗动作仲裁系统（处理出牌、使用消耗品、装备装备等动作）
    processors.add(PlayCardsActionSystem(dbg_game))
    # 可传递卡牌转移系统：出牌时从源手牌移除本体，并 copy 到每个目标手牌（新 uuid）
    processors.add(TransferCardsActionSystem(dbg_game))
    processors.add(UseConsumableItemActionSystem(dbg_game))
    processors.add(EquipGearItemActionSystem(dbg_game))

    # 过回合动作系统
    processors.add(PassTurnActionSystem(dbg_game))

    # 战斗动作后处理系统（如将出牌移至弃牌堆、消耗牌等）
    processors.add(DiscardCardsActionSystem(dbg_game))
    processors.add(ExhaustCardsActionSystem(dbg_game))
    processors.add(ExhaustEtherealCardsSystem(dbg_game))

    # 仲裁系统：出牌、使用消耗品
    processors.add(PlayCardsArbitrationSystem(dbg_game))
    processors.add(UseConsumableItemArbitrationSystem(dbg_game))

    # 回合结束仲裁系统（监视 PassTurnAction，扫全场持有回合结束词缀卡牌的角色并并发仲裁）
    processors.add(TurnEndArbitrationSystem(dbg_game))

    # 仲裁之后可能触发的系统（如死亡判定）
    processors.add(DeathSystem(dbg_game))

    # 回合完成判定系统
    processors.add(CombatRoundCompletionSystem(dbg_game))

    # 战斗回合清理系统（清除旧回合手牌状态）
    processors.add(CombatRoundCleanupSystem(dbg_game))

    # 检查战斗结果系统（必须在死亡标记之后，才能在同一周期内根据最终存活情况判定胜负）
    processors.add(CombatOutcomeSystem(dbg_game))

    # 战斗回合过渡系统（创建新回合 + 生成 action_order）
    processors.add(
        CombatRoundTransitionSystem(
            dbg_game, strategy=ActionOrderStrategy.CREATION_ORDER
        )
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
