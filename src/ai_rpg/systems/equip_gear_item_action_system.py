"""装备前置动作系统模块。"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..utils import prompt_builder
from ..models import (
    AgentEvent,
    EquippedGearComponent,
    InventoryComponent,
    EquipGearItemAction,
    GearItem,
)


#######################################################################################################################################
@prompt_builder
def _build_gear_notice(
    target_name: str,
    item_name: str,
    round_number: int,
) -> str:
    """生成装备使用广播通知。"""
    return (
        f"【第 {round_number} 回合 · 装备行动】\n"
        f"「{target_name}」装备了「{item_name}」。"
    )


#######################################################################################################################################
@final
class EquipGearItemActionSystem(ReactiveProcessor):
    """使用装备前置动作系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    def _return_previously_equipped_gear(
        self, owner_entity: Entity, target_entity: Entity
    ) -> None:
        """换装专用的状态转移：若目标已装备其它装备，将其归还背包持有者（owner_entity）
        的 InventoryComponent，再移除目标的 EquippedGearComponent；未装备则跳过。"""

        if not target_entity.has(EquippedGearComponent):
            return

        previous_item = target_entity.get(EquippedGearComponent).item
        target_entity.remove(EquippedGearComponent)

        owner_inventory = owner_entity.get(InventoryComponent)
        owner_inventory.items.append(previous_item)
        logger.debug(
            f"EquipGearItemActionSystem: {target_entity.name} 换装，已将旧装备 "
            f"{previous_item.name!r} 归还 {owner_entity.name} 的 InventoryComponent"
        )

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(EquipGearItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(EquipGearItemAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("EquipGearItemActionSystem: 战斗未进行中，跳过")
            return

        # 不可能有多个
        assert (
            len(entities) == 1
        ), f"EquipGearItemActionSystem: 同一时间不应有多个实体触发 EquipGearItemAction，当前数量: {len(entities)}"
        logger.debug(f"EquipGearItemActionSystem: 触发实体数量 {len(entities)}")

        # 取出触发实体
        entity = entities[0]

        # 准备数据
        action = entity.get(EquipGearItemAction)

        # 校验 action.item 类型
        item = action.item
        assert isinstance(
            item, GearItem
        ), f"EquipGearItemActionSystem: action.item 应为 GearItem，但实际类型为 {type(item)}"

        # 目标校验
        assert (
            len(action.targets) > 0
        ), "EquipGearItemActionSystem: 使用装备必须指定至少一个目标"
        target_name = action.targets[0]
        logger.debug(
            f"EquipGearItemActionSystem: 使用装备 '{item.name}' | 目标: {action.targets}"
        )

        # 装备到目标实体。前置校验由 activate_equip_gear 负责，这里只落地动作效果。
        target_entity = self._game.get_entity_by_name(target_name)
        assert (
            target_entity is not None
        ), f"EquipGearItemActionSystem: 无法找到目标 {target_name}"

        # 移动语义：装备背包持有者（entity）必须持有 InventoryComponent，装备将从其
        # InventoryComponent.items 中移出，而非拷贝。
        assert entity.has(
            InventoryComponent
        ), f"EquipGearItemActionSystem: {entity.name} 缺少 InventoryComponent"

        # 若目标已装备其它装备（换装场景），先将旧装备归还给背包持有者（entity）。
        self._return_previously_equipped_gear(
            owner_entity=entity, target_entity=target_entity
        )

        # 将本次装备的道具从背包持有者的 InventoryComponent 中移出（对象引用移动，非拷贝）。
        inventory = entity.get(InventoryComponent)
        inventory.items[:] = [
            inventory_item
            for inventory_item in inventory.items
            if inventory_item is not item
        ]

        # 装备动作落地：直接挂载对象引用，而非 model_copy 出的副本。
        target_entity.replace(
            EquippedGearComponent,
            target_entity.name,
            item,
        )
        logger.debug(
            f"EquipGearItemActionSystem: [{entity.name}] 已为 [{target_name}] 装备 '{item.name}'"
        )

        # 向场景内所有存活角色广播装备使用通知
        round_number = len(self._game.current_dungeon_combat_room.combat.rounds)
        stage_entity = self._game.resolve_stage_entity(entity)
        assert (
            stage_entity is not None
        ), f"EquipGearItemActionSystem: 无法找到 {entity.name} 所在的场景实体"
        self._game.broadcast_to_stage(
            entity=entity,
            agent_event=AgentEvent(
                message=_build_gear_notice(
                    target_entity.name,
                    item.name,
                    round_number,
                )
            ),
            exclude_entities={stage_entity},
        )
