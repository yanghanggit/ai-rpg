"""使用消耗品动作系统模块：先扣减队伍背包库存，再把消耗品的内置卡牌物化为手牌。

与装备的区别是消耗品一次性（物化出的卡不可回收），且一次使用消耗整条选定库存，
扣库存成功后才物化；物化数量 = 每个内置牌 × 本次消耗的份数。
"""

from typing import Dict, Final, List, final
from uuid import uuid4

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    Card,
    ConsumableItem,
    HandComponent,
    InventoryComponent,
    NoneEvent,
    RoundEntryKind,
    UseConsumableItemAction,
    remove_item_by_uuid,
)
from ..utils import prompt_builder


#######################################################################################################################################
@prompt_builder
def _build_consumable_notice(
    actor_name: str,
    item_name: str,
    card_names: List[str],
    round_number: int,
) -> str:
    """生成消耗品物化广播通知。"""
    cards_str = "、".join(card_names)
    return (
        f"【第 {round_number} 回合 · 消耗品行动】\n"
        f"「{actor_name}」使用了消耗品「{item_name}」，生成手牌「{cards_str}」。"
    )


#######################################################################################################################################
@final
class UseConsumableItemActionSystem(ReactiveProcessor):
    """消耗品使用系统：先扣减队伍背包库存，再把消耗品内置卡牌物化进当前行动者手牌。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(UseConsumableItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseConsumableItemAction) and entity.has(HandComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("UseConsumableItemActionSystem: 战斗未进行中，跳过")
            return

        assert (
            len(entities) == 1
        ), f"UseConsumableItemActionSystem: 同一时间不应有多个实体触发使用消耗品，当前数量={len(entities)}"

        entity = entities[0]
        action = entity.get(UseConsumableItemAction)
        item = action.item

        logger.debug(
            f"UseConsumableItemActionSystem: [{entity.name}] 使用消耗品 '{item.name}'"
        )

        if not item.cards:
            logger.error(
                f"[UseConsumableItemActionSystem] {entity.name} 使用 '{item.name}' 失败：无内置卡牌"
            )
            return

        # 先扣库存：按 uuid 移除整条消耗品（消耗其全部 count）；扣库存成功后才物化。
        player_entity = self._game.get_player_entity()
        assert (
            player_entity is not None
        ), "UseConsumableItemActionSystem: player_entity is None"
        assert player_entity.has(
            InventoryComponent
        ), "UseConsumableItemActionSystem: player 缺少 InventoryComponent"

        inventory_comp = player_entity.get(InventoryComponent)
        updated_items, removed_item = remove_item_by_uuid(
            inventory_comp.items, item.uuid
        )
        if removed_item is None:
            logger.warning(
                f"UseConsumableItemActionSystem: [{entity.name}] 队伍背包中未找到 "
                f"'{item.name}'，跳过本次使用（不物化）"
            )
            return
        assert isinstance(
            removed_item, ConsumableItem
        ), f"UseConsumableItemActionSystem: 库存条目 '{item.name}' 不是 ConsumableItem"
        player_entity.replace(InventoryComponent, inventory_comp.name, updated_items)

        # 物化：每个内置牌 × 本次消耗份数（removed_item.count）。消耗品卡固定 0 费、一次性；
        # 物化为手牌后强制 retain（跨回合保留直到打出，避免未打出的消耗品卡落入弃牌堆被重新抽到
        # 而重复生效）。不叠加角色属性——Card.damage 即最终值。
        cards = self._materialize_cards(entity, removed_item)
        card_names = [card.name for card in cards]

        # 将生成的多张卡牌放入当前行动者手牌
        hand_comp = entity.get(HandComponent)
        hand_comp.cards.extend(cards)

        # 记录本回合消耗品使用结果（与装备记录同队列）
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        if latest_round is not None:
            latest_round.record(
                RoundEntryKind.CONSUMABLE,
                f"[{entity.name} 使用 {item.name} ×{removed_item.count}] "
                f"生成手牌「{'、'.join(card_names)}」",
                "；".join(card.description for card in cards),
            )

        # 向场景内其他角色广播消耗品使用通知
        round_number = len(self._game.current_dungeon_combat_room.combat.rounds)
        stage_entity = self._game.resolve_stage_entity(entity)
        assert (
            stage_entity is not None
        ), f"UseConsumableItemActionSystem: 无法找到 {entity.name} 所在的场景实体"
        self._game.broadcast_to_stage(
            entity=entity,
            agent_event=NoneEvent(
                message=_build_consumable_notice(
                    entity.name,
                    item.name,
                    card_names,
                    round_number,
                )
            ),
            exclude_entities={stage_entity},
        )

    ####################################################################################################################################
    def _materialize_cards(self, entity: Entity, item: ConsumableItem) -> List[Card]:
        """把 ConsumableItem.cards 复制物化为手牌：每个内置牌生成 item.count 份。"""

        cards: List[Card] = []
        for spec in item.cards:
            # 每个内置牌 × count：count 份各自独立副本。
            for _ in range(item.count):
                card = spec.model_copy(deep=True)
                # 手牌是一张独立副本，必须重新生成 uuid（exhaust/discard 系统按 uuid 定位）
                card.uuid = str(uuid4())
                card.source = entity.name
                # 一次性：打出后进 ExhaustPile。
                card.exhaust = True
                # 未打出时跨回合保留在手牌，避免落入弃牌堆后被重新抽到而重复生效。
                card.retain = True
                cards.append(card)

        return cards
