"""使用消耗品前置动作系统模块。

响应 UseConsumableItemAction 事件，从 InventoryComponent 移除已使用的消耗品，
并向场景广播使用通知，作为后续仲裁系统（UseConsumableItemArbitrationSystem）的前置步骤。

注意：使用消耗品不消耗 energy，玩家在己方行动阶段内可任意次使用。
"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    AgentEvent,
    InventoryComponent,
    UseConsumableItemAction,
)


#######################################################################################################################################
def _generate_use_consumable_context_prompt(
    action: UseConsumableItemAction,
    round_number: int,
) -> str:
    """生成消耗品使用上下文消息，注入角色的对话历史。"""
    item = action.item
    targets_str = "、".join(action.targets) if action.targets else "自身"
    lines = [
        f"【第 {round_number} 回合 · 使用消耗品】",
        f"你使用了消耗品「{item.name}」。",
        f"目标：{targets_str}",
    ]
    return "\n".join(lines)


#######################################################################################################################################
def _generate_action_notice_for_others(
    actor_name: str, item_name: str, round_number: int
) -> str:
    """生成消耗品使用预告，广播给场景内其他角色。"""
    actor_short_name = actor_name.split(".")[-1]
    item_short_name = item_name.split(".")[-1] if "." in item_name else item_name
    return f"【第 {round_number} 回合】{actor_short_name} 使用了消耗品「{item_short_name}」。"


#######################################################################################################################################
@final
class UseConsumableItemActionSystem(ReactiveProcessor):
    """使用消耗品前置动作系统。

    从 InventoryComponent 扣减消耗品数量（耗尽则移除），广播使用通知，
    并注入出牌者的对话上下文；不消耗 energy，不推进回合。
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(UseConsumableItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(UseConsumableItemAction)
            and entity.has(InventoryComponent)
            and entity.has(ActorComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
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

        for entity in entities:
            action = entity.get(UseConsumableItemAction)
            item = action.item

            logger.debug(
                f"UseConsumableItemActionSystem: [{entity.name}] 使用消耗品 '{item.name}'"
                f" | target_type={item.target_type} | 目标: {action.targets}"
            )

            # 从 InventoryComponent 扣减 count，耗尽则移除该条目
            inventory_comp = entity.get(InventoryComponent)
            updated_items = []
            consumed = False
            for inv_item in inventory_comp.items:
                if not consumed and inv_item.name == item.name:
                    consumed = True
                    if inv_item.count > 1:
                        # 直接修改 count（MutableComponent 允许就地修改）
                        inv_item.count -= 1
                        updated_items.append(inv_item)
                    # count == 1：不追加，即移除
                else:
                    updated_items.append(inv_item)

            if not consumed:
                logger.warning(
                    f"UseConsumableItemActionSystem: [{entity.name}] 背包中未找到 '{item.name}'，跳过扣减"
                )
            else:
                inventory_comp.items = updated_items
                logger.debug(
                    f"UseConsumableItemActionSystem: [{entity.name}] 消耗品 '{item.name}' 扣减完毕，"
                    f"剩余背包道具: {[i.name for i in inventory_comp.items]}"
                )

            # 为使用者注入本回合使用消耗品的上下文
            self._game.add_human_message(
                entity=entity,
                message_content=_generate_use_consumable_context_prompt(
                    action=action,
                    round_number=len(current_rounds),
                ),
            )

            # 向场景内其他角色广播使用预告
            stage_entity = self._game.resolve_stage_entity(entity)
            assert (
                stage_entity is not None
            ), f"UseConsumableItemActionSystem: 无法找到 {entity.name} 所在的场景实体"
            self._game.broadcast_to_stage(
                entity=entity,
                agent_event=AgentEvent(
                    message=_generate_action_notice_for_others(
                        actor_name=action.name,
                        item_name=item.name,
                        round_number=len(current_rounds),
                    )
                ),
                exclude_entities={entity, stage_entity},
            )
