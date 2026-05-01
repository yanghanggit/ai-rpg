"""过牌动作系统模块。

处理战斗中角色的跳过出牌动作，消耗 1 点 energy 并推进行动顺序，不打出任何卡牌。
仅在战斗进行中(ongoing)阶段执行。
"""

from typing import Final, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    PassTurnAction,
    ActorComponent,
    AgentEvent,
    RoundStatsComponent,
)
from ..game.tcg_game import TCGGame


#######################################################################################################################################
def _generate_pass_turn_context_prompt(actor_name: str, round_number: int) -> str:
    """生成过牌上下文消息，注入角色的对话历史。"""
    return "\n".join(
        [
            f"【第 {round_number} 回合 · 过牌】",
            "你选择跳过本次出牌机会。",
        ]
    )


#######################################################################################################################################
def _generate_pass_turn_notice_for_others(actor_name: str, round_number: int) -> str:
    """生成过牌预告，广播给场景内其他角色。"""
    actor_short_name = actor_name.split(".")[-1]
    return f"【第 {round_number} 回合】{actor_short_name} 选择跳过出牌。"


#######################################################################################################################################
@final
class PassTurnActionSystem(ReactiveProcessor):
    """过牌动作系统。

    响应 PassTurnAction 组件的添加事件，消耗当前行动者的 1 点 energy 并推进行动顺序。
    不打出任何卡牌，不触发仲裁。

    触发条件：
    - 实体添加 PassTurnAction 组件
    - 战斗序列处于进行中(ongoing)状态
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PassTurnAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PassTurnAction)
            and entity.has(HandComponent)
            and entity.has(ActorComponent)
            and entity.has(RoundStatsComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("PassTurnActionSystem: 战斗未进行中，跳过过牌处理")
            return

        assert len(entities) == 1, "PassTurnActionSystem: 一次只能处理一个过牌动作实体"

        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None
        ), "PassTurnActionSystem: current_rounds is None"

        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None, "PassTurnActionSystem: latest_round is None"

        for entity in entities:
            pass_turn_action = entity.get(PassTurnAction)
            logger.debug(f"  [{pass_turn_action.name}] 选择过牌（跳过出牌机会）")

            assert entity.name == self._game.get_current_turn_actor(last_round), (
                f"PassTurnActionSystem: 过牌角色 {entity.name} 不是当前 turn 的行动者！"
                f" current_turn_actor={self._game.get_current_turn_actor(last_round)}"
            )

            last_round.completed_actors.append(pass_turn_action.name)

            round_stats = entity.get(RoundStatsComponent)
            assert (
                round_stats.energy > 0
            ), f"{entity.name} 能量不足，无法过牌！当前 energy={round_stats.energy}"

            entity.replace(
                RoundStatsComponent,
                entity.name,
                round_stats.energy - 1,
                round_stats.block,
            )

            last_round.current_turn_actor_name = self._game.get_current_turn_actor(
                last_round
            )

            logger.debug(
                f"  completed_actors: {last_round.completed_actors} / "
                f"current_turn_actor_name={last_round.current_turn_actor_name}"
            )

            self._game.add_human_message(
                entity=entity,
                message_content=_generate_pass_turn_context_prompt(
                    actor_name=pass_turn_action.name,
                    round_number=len(current_rounds),
                ),
            )

            stage_entity = self._game.resolve_stage_entity(entity)
            assert (
                stage_entity is not None
            ), f"PassTurnActionSystem: 无法找到 {entity.name} 所在的场景实体"
            self._game.broadcast_to_stage(
                entity=entity,
                agent_event=AgentEvent(
                    message=_generate_pass_turn_notice_for_others(
                        actor_name=pass_turn_action.name,
                        round_number=len(current_rounds),
                    )
                ),
                exclude_entities={entity, stage_entity},
            )
