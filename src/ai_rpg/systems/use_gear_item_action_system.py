"""使用装备前置动作系统模块。"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    EquippedGearComponent,
    InventoryComponent,
    MonsterComponent,
    PartyMemberComponent,
    UseGearItemAction,
    GearItem,
)


#######################################################################################################################################
def _generate_party_notice(
    action: UseGearItemAction,
    round_number: int,
) -> str:
    """生成友方阵营视角的装备使用通知（PartyMemberComponent 角色接收）。"""
    target_name = action.targets[0] if action.targets else "未知目标"
    return (
        f"【第 {round_number} 回合 · 友方行动】\n"
        f"「{target_name}」装备了「{action.item.name}」。"
    )


#######################################################################################################################################
def _generate_enemy_notice(
    action: UseGearItemAction,
    round_number: int,
) -> str:
    """生成敌方视角的装备使用通知（MonsterComponent 角色接收）。"""
    target_name = action.targets[0] if action.targets else "未知目标"
    return (
        f"【第 {round_number} 回合 · 敌方行动】\n"
        f"敌方为 {target_name} 装备了「{action.item.name}」。"
    )


#######################################################################################################################################
@final
class UseGearItemActionSystem(ReactiveProcessor):
    """使用装备前置动作系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    def _remove_equipped_gear_globally(self, item_name: str) -> None:
        """扫描全局：移除所有持有同名装备的 EquippedGearComponent（保证全局唯一）。"""
        for holder in self._game.get_group(
            Matcher(EquippedGearComponent)
        ).entities.copy():
            if holder.get(EquippedGearComponent).item.name == item_name:
                logger.debug(
                    f"UseGearItemActionSystem: 从 [{holder.name}] 移除已激活装备 '{item_name}'"
                )
                holder.remove(EquippedGearComponent)

    ####################################################################################################################################
    def _deduct_gear_durability(self, entity: Entity, item: GearItem) -> None:
        """扣减 InventoryComponent 中原始 GearItem 的耐久度。"""
        inventory_comp = entity.get(InventoryComponent)
        for inventory_item in inventory_comp.items:
            if inventory_item.uuid == item.uuid:
                assert isinstance(
                    inventory_item, GearItem
                ), f"UseGearItemActionSystem: uuid 匹配到的物品非 GearItem: {inventory_item}"
                inventory_item.durability -= 1
                inventory_item.durability = max(inventory_item.durability, 0)
                logger.debug(
                    f"UseGearItemActionSystem: '{item.name}' 耐久 {inventory_item.durability + 1} → {inventory_item.durability}"
                )
                break

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(UseGearItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseGearItemAction) and entity.has(InventoryComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("UseGearItemActionSystem: 战斗未进行中，跳过")
            return

        assert (
            len(entities) == 1
        ), f"UseGearItemActionSystem: 同一时间不应有多个实体触发 UseGearItemAction，当前数量: {len(entities)}"
        logger.debug(f"UseGearItemActionSystem: 触发实体数量 {len(entities)}")

        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None
        ), "UseGearItemActionSystem: current_rounds is None"

        entity = entities[0]
        action = entity.get(UseGearItemAction)
        item = action.item
        assert isinstance(
            item, GearItem
        ), f"UseGearItemActionSystem: action.item 应为 GearItem，但实际类型为 {type(item)}"

        assert (
            len(action.targets) > 0
        ), "UseGearItemActionSystem: 使用装备必须指定至少一个目标"
        target_name = action.targets[0]

        logger.debug(
            f"UseGearItemActionSystem: 使用装备 '{item.name}'"
            f" | target_type={item.target_type} | 目标: {action.targets}"
        )

        # 保证全局唯一：移除所有持有同名装备的 EquippedGearComponent
        self._remove_equipped_gear_globally(item.name)

        # 装备到目标实体（item 引用自 action，始终与 inventory 中同一对象）
        target_entity = self._game.get_entity_by_name(target_name)
        assert (
            target_entity is not None
        ), f"UseGearItemActionSystem: 无法找到目标 {target_name}"
        target_entity.replace(
            EquippedGearComponent,
            target_entity.name,
            item.model_copy(deep=True),
        )
        logger.debug(
            f"UseGearItemActionSystem: [{entity.name}] 已为 [{target_name}] 装备 '{item.name}'"
        )

        # 扣减背包中的装备耐久度
        self._deduct_gear_durability(entity, item)

        # 向场景内所有存活角色按阵营注入行动通知上下文
        round_number = len(current_rounds)
        actor_entities = self._game.get_alive_actors_in_stage(entity)
        for actor in actor_entities:
            if actor.has(PartyMemberComponent):
                self._game.add_human_message(
                    entity=actor,
                    message_content=_generate_party_notice(action, round_number),
                )
            elif actor.has(MonsterComponent):
                self._game.add_human_message(
                    entity=actor,
                    message_content=_generate_enemy_notice(action, round_number),
                )
