"""使用装备前置动作系统模块。"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    AgentEvent,
    EquippedGearComponent,
    InventoryComponent,
    UseGearItemAction,
    GearItem,
)


#######################################################################################################################################
def _generate_use_gear_context_prompt(
    action: UseGearItemAction,
    round_number: int,
) -> str:
    """生成装备使用上下文消息，注入角色的对话历史。"""
    item = action.item
    targets_str = "、".join(action.targets) if action.targets else "自身"
    lines = [
        f"【第 {round_number} 回合 · 使用装备】",
        f"你使用了装备「{item.name}」。",
        f"目标：{targets_str}",
    ]
    return "\n".join(lines)


#######################################################################################################################################
def _generate_action_notice_for_others(
    item_name: str,
    target_name: str,
    round_number: int,
) -> str:
    """生成装备使用预告，广播给场景内其他角色。"""
    return f"【第 {round_number} 回合】友方阵营为 {target_name} 装备了「{item_name}」。"


#######################################################################################################################################
@final
class UseGearItemActionSystem(ReactiveProcessor):
    """使用装备前置动作系统。"""

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(UseGearItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(UseGearItemAction)
            and entity.has(InventoryComponent)
            and entity.has(ActorComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("UseGearItemActionSystem: 战斗未进行中，跳过")
            return

        logger.debug(f"UseGearItemActionSystem: 触发实体数量 {len(entities)}")

        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None
        ), "UseGearItemActionSystem: current_rounds is None"

        for entity in entities:
            action = entity.get(UseGearItemAction)
            item = action.item
            target_name = action.targets[0] if action.targets else entity.name

            logger.debug(
                f"UseGearItemActionSystem: [{entity.name}] 使用装备 '{item.name}'"
                f" | target_type={item.target_type} | 目标: {action.targets}"
            )

            # 扫描全局：移除所有持有同名装备的 EquippedGearComponent（保证全局唯一）
            for holder in self._game.get_group(
                Matcher(EquippedGearComponent)
            ).entities.copy():
                if holder.get(EquippedGearComponent).item.name == item.name:
                    logger.debug(
                        f"UseGearItemActionSystem: 从 [{holder.name}] 移除已激活装备 '{item.name}'"
                    )
                    holder.remove(EquippedGearComponent)

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

            # 扣减 InventoryComponent 中原始 GearItem 的耐久度
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

            # 为使用者注入本回合使用装备的上下文
            self._game.add_human_message(
                entity=entity,
                message_content=_generate_use_gear_context_prompt(
                    action=action,
                    round_number=len(current_rounds),
                ),
            )

            # 向场景内其他角色广播使用预告
            stage_entity = self._game.resolve_stage_entity(entity)
            assert (
                stage_entity is not None
            ), f"UseGearItemActionSystem: 无法找到 {entity.name} 所在的场景实体"
            self._game.broadcast_to_stage(
                entity=entity,
                agent_event=AgentEvent(
                    message=_generate_action_notice_for_others(
                        item_name=item.name,
                        target_name=target_name,
                        round_number=len(current_rounds),
                    )
                ),
                exclude_entities={entity, stage_entity},
            )
