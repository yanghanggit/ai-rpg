"""使用消耗品动作系统模块。

处理战斗中角色使用消耗品的动作：消耗 1 点 energy、从背包中移除/递减物品、
向对话历史注入使用上下文、向场景广播行动预告。
仅在战斗进行中(ongoing)阶段执行。
"""

from typing import Final, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    UseConsumableItemAction,
    ActorComponent,
    AgentEvent,
    RoundStatsComponent,
    InventoryComponent,
)
from ..game.tcg_game import TCGGame


#######################################################################################################################################
def _generate_use_item_context_prompt(
    action: UseConsumableItemAction,
    round_number: int,
) -> str:
    """生成使用消耗品的上下文消息，注入角色的对话历史。"""
    targets_str = "、".join(action.targets) if action.targets else "自身"
    lines = [
        f"【第 {round_number} 回合 · 使用消耗品】",
        f"你使用了消耗品「{action.item.name}」。",
        f"目标：{targets_str}",
    ]
    if action.item.description:
        lines.append(f"物品描述：{action.item.description}")
    return "\n".join(lines)


#######################################################################################################################################
def _generate_item_notice_for_others(
    actor_name: str, item_name: str, round_number: int
) -> str:
    """生成使用消耗品预告，广播给场景内其他角色。"""
    actor_short_name = actor_name.split(".")[-1]
    return f"【第 {round_number} 回合】{actor_short_name} 使用了消耗品「{item_name}」。"


#######################################################################################################################################
@final
class UseConsumableItemActionSystem(ReactiveProcessor):
    """使用消耗品动作系统。

    响应 UseConsumableItemAction 事件，消耗 1 点 energy、从背包移除/递减物品、
    注入使用上下文到对话历史并广播行动预告。仲裁由 UseConsumableItemArbitrationSystem 独立处理。

    触发条件：
    - 实体添加 UseConsumableItemAction 组件
    - 战斗序列处于进行中(ongoing)状态
    - 仅当前 turn 行动者可触发（assert 守卫）
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(UseConsumableItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(UseConsumableItemAction)
            and entity.has(ActorComponent)
            and entity.has(RoundStatsComponent)
            and entity.has(InventoryComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("UseConsumableItemActionSystem: 战斗未进行中，跳过")
            return

        assert (
            len(entities) == 1
        ), "UseConsumableItemActionSystem: 一次只能处理一个使用消耗品动作实体"

        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None
        ), "UseConsumableItemActionSystem: current_rounds is None"

        last_round = self._game.current_dungeon.latest_round
        assert (
            last_round is not None
        ), "UseConsumableItemActionSystem: latest_round is None"

        for entity in entities:
            action = entity.get(UseConsumableItemAction)
            logger.debug(
                f"  [{action.name}] 使用消耗品 → {action.item.name}"
                f" | targets: {action.targets}"
            )

            assert entity.name == self._game.get_current_turn_actor(last_round), (
                f"UseConsumableItemActionSystem: 使用者 {entity.name} 不是当前 turn 的行动者！"
                f" current_turn_actor={self._game.get_current_turn_actor(last_round)}"
            )

            last_round.completed_actors.append(action.name)

            # 消耗 1 点 energy
            self._game.consume_energy(entity)

            # 推进行动顺序
            self._game.advance_turn(last_round)

            logger.debug(
                f"  completed_actors: {last_round.completed_actors} / "
                f"current_turn_actor_name={last_round.current_turn_actor_name}"
            )

            # 从背包移除或递减消耗品（按 uuid 精确匹配）
            self._game.consume_item_from_inventory(entity, action.item)

            # 注入使用上下文到对话历史
            self._game.add_human_message(
                entity=entity,
                message_content=_generate_use_item_context_prompt(
                    action=action,
                    round_number=len(current_rounds),
                ),
            )

            # 广播行动预告给场景内其他角色
            stage_entity = self._game.resolve_stage_entity(entity)
            assert (
                stage_entity is not None
            ), f"UseConsumableItemActionSystem: 无法找到 {entity.name} 所在的场景实体"
            self._game.broadcast_to_stage(
                entity=entity,
                agent_event=AgentEvent(
                    message=_generate_item_notice_for_others(
                        actor_name=action.name,
                        item_name=action.item.name,
                        round_number=len(current_rounds),
                    )
                ),
                exclude_entities={entity, stage_entity},
            )
