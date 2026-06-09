"""使用装备前置动作系统模块。

响应 UseGearItemAction 事件，从 InventoryComponent 移除被使用的装备，
并将其挂载到目标的 EquippedGearComponent（替换逻辑），随后广播使用通知。
"""

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
    actor_name: str,
    item_name: str,
    target_name: str,
    round_number: int,
) -> str:
    """生成装备使用预告，广播给场景内其他角色。"""
    actor_short_name = actor_name.split(".")[-1]
    item_short_name = item_name.split(".")[-1] if "." in item_name else item_name
    target_short_name = target_name.split(".")[-1]
    return (
        f"【第 {round_number} 回合】{actor_short_name} 为 {target_short_name}"
        f" 装备了「{item_short_name}」。"
    )


#######################################################################################################################################
@final
class UseGearItemActionSystem(ReactiveProcessor):
    """使用装备前置动作系统。

    从 InventoryComponent 扣减装备数量（耗尽则移除），将装备挂载到目标
    EquippedGearComponent（替换旧装备），广播使用通知并注入对话上下文。
    """

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

            # 从 InventoryComponent 移除装备（装备 count 必为 1，直接移除）
            inventory_comp = entity.get(InventoryComponent)
            inv_idx = next(
                (
                    i
                    for i, inv_item in enumerate(inventory_comp.items)
                    if inv_item.name == item.name
                ),
                None,
            )
            if inv_idx is None:
                logger.warning(
                    f"UseGearItemActionSystem: [{entity.name}] 背包中未找到 '{item.name}'，跳过装备"
                )
                continue

            assert (
                inventory_comp.items[inv_idx].count == 1
            ), f"装备 '{item.name}' count 必为 1，实际为 {inventory_comp.items[inv_idx].count}"
            inventory_comp.items.pop(inv_idx)

            # 装备到目标实体：替换逻辑（单件装备槽）
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
                        actor_name=action.name,
                        item_name=item.name,
                        target_name=target_name,
                        round_number=len(current_rounds),
                    )
                ),
                exclude_entities={entity, stage_entity},
            )
