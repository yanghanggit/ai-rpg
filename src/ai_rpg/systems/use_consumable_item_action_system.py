"""使用消耗品前置动作系统模块。"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import deduct_item_from_inventory
from ..models import (
    AgentEvent,
    InventoryComponent,
    UseConsumableItemAction,
)


#######################################################################################################################################
def _generate_consumable_notice(
    actor_name: str,
    action: UseConsumableItemAction,
    round_number: int,
) -> str:
    """生成消耗品使用广播通知。"""
    targets_str = "、".join(action.targets) if action.targets else "无"
    return (
        f"【第 {round_number} 回合 · 消耗品行动】\n"
        f"「{actor_name}」使用了消耗品「{action.item.name}」，目标：{targets_str}。"
    )


#######################################################################################################################################
@final
class UseConsumableItemActionSystem(ReactiveProcessor):
    """消耗品使用前置动作系统：扣减库存 + 按阵营广播通知上下文。"""

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
        return entity.has(UseConsumableItemAction) and entity.has(InventoryComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("UseConsumableItemActionSystem: 战斗未进行中，跳过")
            return

        logger.debug(
            f"UseConsumableItemActionSystem: 触发 {len(entities)} 个体使用消耗品前置动作系统"
        )
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
        consumed = deduct_item_from_inventory(entity, item)
        if not consumed:
            logger.warning(
                f"UseConsumableItemActionSystem: [{entity.name}] 背包中未找到 '{item.name}'，跳过扣减"
            )
        else:
            logger.debug(
                f"UseConsumableItemActionSystem: [{entity.name}] 消耗品 '{item.name}' 扣减完毕，"
                f"剩余背包道具: {[i.name for i in entity.get(InventoryComponent).items]}"
            )

        # 向场景内所有存活角色广播消耗品使用通知
        stage_entity = self._game.resolve_stage_entity(entity)
        assert (
            stage_entity is not None
        ), f"UseConsumableItemActionSystem: 无法找到 {entity.name} 所在的场景实体"
        self._game.broadcast_to_stage(
            entity=entity,
            agent_event=AgentEvent(
                message=_generate_consumable_notice(
                    entity.name,
                    action,
                    len(self._game.current_combat_room.combat.rounds),
                )
            ),
            exclude_entities={stage_entity},
        )
