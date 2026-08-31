"""装备转化系统模块：将 GearItem 的 cards 直接物化为多张 Card 放入当前行动者手牌。"""

from typing import Dict, Final, List, final
from uuid import uuid4

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import compute_character_stats
from ..game.dbg_game import DBGGame
from ..models import (
    AgentEvent,
    Card,
    EquipGearItemAction,
    EquippedGearComponent,
    GearItem,
    HandComponent,
    InventoryComponent,
    PartyMemberComponent,
)
from ..utils import prompt_builder


#######################################################################################################################################
@prompt_builder
def _build_gear_notice(
    actor_name: str,
    item_name: str,
    card_names: List[str],
    round_number: int,
) -> str:
    """生成装备转化广播通知。"""
    cards_str = "、".join(card_names)
    return (
        f"【第 {round_number} 回合 · 装备行动】\n"
        f"「{actor_name}」将「{item_name}」转化为手牌「{cards_str}」。"
    )


#######################################################################################################################################
@final
class EquipGearItemActionSystem(ReactiveProcessor):
    """装备转化系统：把团队背包内的 GearItem 物化为 Card 放入当前行动者手牌。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(EquipGearItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(EquipGearItemAction) and entity.has(HandComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("EquipGearItemActionSystem: 战斗未进行中，跳过")
            return

        assert (
            len(entities) == 1
        ), f"EquipGearItemActionSystem: 同一时间不应有多个实体触发 EquipGearItemAction，当前数量: {len(entities)}"

        entity = entities[0]
        action = entity.get(EquipGearItemAction)
        item = action.item
        assert isinstance(
            item, GearItem
        ), f"EquipGearItemActionSystem: action.item 应为 GearItem，但实际类型为 {type(item)}"

        assert entity.has(HandComponent), f"{entity.name} 缺少 HandComponent"
        assert entity.has(PartyMemberComponent), f"{entity.name} 不是友方角色"

        # 直接复制 GearItem.cards 物化为多张 Card，无需再调用 LLM
        cards = self._materialize_cards(entity, item)
        if not cards:
            logger.error(f"[EquipGearItemActionSystem] {entity.name} 转化装备失败")
            return

        card_names = [card.name for card in cards]

        # 团队背包：装备统一由 player 持有，从 player 背包移除（移动语义）
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "玩家实体不存在！"
        assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"
        inventory = player_entity.get(InventoryComponent)
        inventory.items[:] = [
            inventory_item
            for inventory_item in inventory.items
            if inventory_item is not item
        ]

        # 登记到当前行动者：战斗结束后由 CombatPileTeardownSystem 归还玩家背包
        if entity.has(EquippedGearComponent):
            entity.get(EquippedGearComponent).items.append(item)
        else:
            entity.add(EquippedGearComponent, entity.name, [item])

        # 将生成的多张卡牌放入当前行动者手牌
        hand_comp = entity.get(HandComponent)
        hand_comp.cards.extend(cards)
        logger.debug(
            f"EquipGearItemActionSystem: [{entity.name}] 将 '{item.name}' 转化为手牌 "
            f"'{'、'.join(card_names)}'"
        )

        # 记录本回合装备使用结果（供 TUI 展示）
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        if latest_round is not None:
            latest_round.gear_combat_log.append(
                f"[{entity.name} 装备 {item.name}] 生成手牌「{'、'.join(card_names)}」"
            )
            latest_round.gear_narrative.append(
                "；".join(card.description for card in cards)
            )
            latest_round.gear_equip_count += 1

        # 向场景内其他角色广播装备转化通知
        round_number = len(self._game.current_dungeon_combat_room.combat.rounds)
        stage_entity = self._game.resolve_stage_entity(entity)
        assert (
            stage_entity is not None
        ), f"EquipGearItemActionSystem: 无法找到 {entity.name} 所在的场景实体"
        self._game.broadcast_to_stage(
            entity=entity,
            agent_event=AgentEvent(
                message=_build_gear_notice(
                    entity.name,
                    item.name,
                    card_names,
                    round_number,
                )
            ),
            exclude_entities={stage_entity},
        )

    ####################################################################################################################################
    def _materialize_cards(
        self,
        entity: Entity,
        gear: GearItem,
    ) -> List[Card]:
        """将 GearItem.cards 复制物化为多张手牌 Card，并叠加当前行动者属性加成。"""

        actor_stats = compute_character_stats(entity)

        cards: List[Card] = []
        for spec in gear.cards:
            card = spec.model_copy(deep=True)
            # 手牌是一张独立副本，必须重新生成 uuid（exhaust/discard 系统按 uuid 定位）
            card.uuid = str(uuid4())
            card.source = entity.name
            # 计算端强制：GearItem 转化的卡牌跨回合保留在手牌（不进入弃牌堆）
            card.retain = True

            # 沿用 fill_draw_pile_system 的思路：卡牌自身值非 0 时，叠加当前行动者属性
            if card.damage != 0:
                card.damage += actor_stats.attack
            if card.block != 0:
                card.block += actor_stats.defense

            cards.append(card)

        return cards
