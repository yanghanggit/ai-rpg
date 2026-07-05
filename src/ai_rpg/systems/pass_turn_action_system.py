"""过牌动作系统模块。"""

from typing import Final, final, Dict, List
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    HumanMessage,
    PassTurnAction,
    ActorComponent,
    AgentEvent,
    RoundStatsComponent,
)
from ..game.dbg_game import DBGGame
from ..game.entity_ops import consume_energy, get_energy


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
    """过牌动作系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
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
    async def react(self, entities: List[Entity]) -> None:

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

            # 消耗过牌角色的全部行动能量，并按消耗次数追加 completed_actors（与出牌系统保持一致）
            cur_energy = get_energy(entity)
            logger.debug(
                f"  {entity.name} 当前剩余行动能量: {cur_energy}，消耗后变为 0"
            )
            consume_energy(entity, cur_energy)
            for _ in range(cur_energy):
                last_round.completed_actors.append(pass_turn_action.name)

            # 结束当前角色的回合，进入下一角色的回合
            self._game.advance_turn(last_round)

            # 输出当前回合状态日志
            logger.debug(
                f"  completed_actors: {last_round.completed_actors} / "
                f"current_turn_actor_name={last_round.current_turn_actor_name}"
            )

            # 给过牌角色发送过牌上下文消息，注入角色的对话历史
            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=_generate_pass_turn_context_prompt(
                        actor_name=pass_turn_action.name,
                        round_number=len(current_rounds),
                    )
                ),
            )

            # 给场景内其他角色广播过牌预告
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
