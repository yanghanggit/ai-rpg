"""使用消耗品前置动作系统模块。"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import get_alive_actors_in_stage
from ..models import (
    HumanMessage,
    InventoryComponent,
    MonsterComponent,
    PartyMemberComponent,
    UseConsumableItemAction,
)


#######################################################################################################################################
def _generate_party_notice(
    action: UseConsumableItemAction,
    round_number: int,
) -> str:
    """生成友方阵营视角的消耗品使用通知（PartyMemberComponent 角色接收）。"""
    targets_str = "、".join(action.targets) if action.targets else "无"
    return (
        f"【第 {round_number} 回合 · 友方行动】\n"
        f"友方阵营使用了消耗品「{action.item.name}」。\n"
        f"目标：{targets_str}"
    )


#######################################################################################################################################
def _generate_enemy_notice(
    action: UseConsumableItemAction,
    round_number: int,
) -> str:
    """生成敌方视角的消耗品使用通知（MonsterComponent 角色接收）。"""
    targets_str = "、".join(action.targets) if action.targets else "无"
    return (
        f"【第 {round_number} 回合 · 敌方行动】\n"
        f"敌方使用了消耗品「{action.item.name}」，目标为 {targets_str}。"
    )


#######################################################################################################################################
@final
class UseConsumableItemActionSystem(ReactiveProcessor):
    """消耗品使用前置动作系统：扣减库存 + 按阵营广播通知上下文。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    def _deduct_item_from_inventory(self, entity: Entity, item_name: str) -> bool:
        """从 InventoryComponent 扣减指定消耗品数量，耗尽则移除该条目。

        Returns:
            True 表示成功找到并扣减，False 表示背包中未找到该物品。
        """
        inventory_comp = entity.get(InventoryComponent)
        updated_items = []
        consumed = False
        for inv_item in inventory_comp.items:
            if not consumed and inv_item.name == item_name:
                consumed = True
                if inv_item.count > 1:
                    # 直接修改 count（MutableComponent 允许就地修改）
                    inv_item.count -= 1
                    updated_items.append(inv_item)
                # count == 1：不追加，即移除
            else:
                updated_items.append(inv_item)
        if consumed:
            inventory_comp.items = updated_items
        return consumed

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(UseConsumableItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseConsumableItemAction) and entity.has(InventoryComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        logger.debug(
            f"UseConsumableItemActionSystem: 触发 {len(entities)} 个体使用消耗品前置动作系统"
        )

        if not self._game.current_dungeon.is_ongoing:
            logger.debug("UseConsumableItemActionSystem: 战斗未进行中，跳过")
            return

        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None
        ), "UseConsumableItemActionSystem: current_rounds is None"

        latest_round = self._game.current_dungeon.latest_round
        assert (
            latest_round is not None
        ), "UseConsumableItemActionSystem: latest_round is None"
        assert (
            latest_round.consumable_use_count == 0
        ), f"UseConsumableItemActionSystem: 本回合已使用过消耗品（consumable_use_count={latest_round.consumable_use_count}），应由 dungeon_actions 拦截"

        assert (
            len(entities) == 1
        ), f"UseConsumableItemActionSystem: 同一时间不应有多个实体触发使用消耗品前置动作，当前数量={len(entities)}"

        entity = entities[0]
        assert entity.has(
            InventoryComponent
        ), f"UseConsumableItemActionSystem: 触发实体 {entity.name} 缺失 InventoryComponent"

        action = entity.get(UseConsumableItemAction)
        item = action.item

        logger.debug(
            f"UseConsumableItemActionSystem: [{entity.name}] 使用消耗品 '{item.name}'"
            f" | target_type={item.target_type} | 目标: {action.targets}"
        )

        # 扣减背包中的消耗品数量
        consumed = self._deduct_item_from_inventory(entity, item.name)
        if not consumed:
            logger.warning(
                f"UseConsumableItemActionSystem: [{entity.name}] 背包中未找到 '{item.name}'，跳过扣减"
            )
        else:
            logger.debug(
                f"UseConsumableItemActionSystem: [{entity.name}] 消耗品 '{item.name}' 扣减完毕，"
                f"剩余背包道具: {[i.name for i in entity.get(InventoryComponent).items]}"
            )

        # 向场景内所有存活角色按阵营注入行动通知上下文
        round_number = len(current_rounds)
        actor_entities = get_alive_actors_in_stage(self._game, entity)
        for actor in actor_entities:
            if actor.has(PartyMemberComponent):
                self._game.add_human_message(
                    entity=actor,
                    human_message=HumanMessage(
                        content=_generate_party_notice(action, round_number)
                    ),
                )
            elif actor.has(MonsterComponent):
                self._game.add_human_message(
                    entity=actor,
                    human_message=HumanMessage(
                        content=_generate_enemy_notice(action, round_number)
                    ),
                )
