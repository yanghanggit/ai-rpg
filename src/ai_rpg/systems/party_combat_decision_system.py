"""队员出牌决策系统：把玩家已决定的出牌 / 过牌记成一条决策记录（无推理，原因留白）。

记录形状与 `MonsterCombatDecisionSystem` 一致，合法性判定复用 `play_blocked_cause`，
因此记录不会与结算层的拦截结论矛盾。设计取舍见 docs/wiki/combat-pipeline.md。
"""

import json
from typing import Dict, Final, List, final, override

from loguru import logger

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    DeathComponent,
    HandComponent,
    HumanMessage,
    PartyMemberComponent,
    PassTurnAction,
    PlayCardsAction,
)
from .combat_decision_common import (
    ACTION_PASS,
    ACTION_PLAY,
    REASON_PLACEHOLDER,
    build_combat_decision_record,
    build_combat_decision_tag,
    play_blocked_cause,
)


#######################################################################################################################################
@final
class PartyCombatDecisionSystem(ReactiveProcessor):
    """为队员的出牌 / 过牌决策补一条决策记录（无推理、原因为占位句）。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        # 出牌与过牌都是「一次决策」，两者都要记录，才能与怪物侧对齐。
        return {
            Matcher(PlayCardsAction): GroupEvent.ADDED,
            Matcher(PassTurnAction): GroupEvent.ADDED,
        }

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            (entity.has(PlayCardsAction) or entity.has(PassTurnAction))
            and entity.has(HandComponent)
            and entity.has(PartyMemberComponent)
            and not entity.has(DeathComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("PartyCombatDecisionSystem: 战斗未进行中，跳过")
            return

        round_number = len(self._game.current_dungeon_combat_room.combat.rounds or [])

        for entity in entities:
            if entity.has(PlayCardsAction):
                self._record_play(entity, round_number)
            elif self._played_this_round(entity, round_number):
                # 出完牌后交出行动权是机械步骤，不是第二次决策：不写记录（与怪物侧同形）。
                logger.debug(
                    f"PartyCombatDecisionSystem: [{entity.name}] 本回合已出牌，交权不另记录"
                )
            else:
                self._record_pass(entity, round_number)

    #######################################################################################################################################
    def _played_this_round(self, entity: Entity, round_number: int) -> bool:
        """本回合是否已出过牌（用于区分「纯过牌」与「出完牌后交权」）。"""
        for message in reversed(self._game.get_agent_memory(entity).messages):
            tag = getattr(message, "combat_decision", None)
            if tag is None:
                continue
            decision = json.loads(tag)
            if decision["round"] < round_number:  # 记录按时间先后：更早的回合不必再看
                break
            if decision["round"] == round_number and decision["action"] == ACTION_PLAY:
                return True
        return False

    #######################################################################################################################################
    def _record_play(self, entity: Entity, round_number: int) -> None:
        action = entity.get(PlayCardsAction)
        card = action.card
        targets = list(action.targets)

        # 结算层（PlayCardsActionSystem）会拦下不可出的牌，记录必须与之一致：本想打、没打出去。
        blocked_cause = play_blocked_cause(card)
        if blocked_cause:
            self._write(
                entity,
                round_number,
                ACTION_PASS,
                card.name,
                [],
                forced_cause=blocked_cause,
                forced_outcome="这次出牌没有发生",
            )
            logger.debug(
                f"PartyCombatDecisionSystem: [{entity.name}] 记录被拦下的出牌决策 '{card.name}'（{blocked_cause}）"
            )
            return

        self._write(entity, round_number, ACTION_PLAY, card.name, targets)
        logger.debug(
            f"PartyCombatDecisionSystem: [{entity.name}] 记录出牌决策 '{card.name}'，目标：{targets}"
        )

    #######################################################################################################################################
    def _record_pass(self, entity: Entity, round_number: int) -> None:
        self._write(entity, round_number, ACTION_PASS, "", [])
        logger.debug(f"PartyCombatDecisionSystem: [{entity.name}] 记录过牌决策")

    #######################################################################################################################################
    def _write(
        self,
        entity: Entity,
        round_number: int,
        action: str,
        card_name: str,
        targets: List[str],
        *,
        forced_cause: str = "",
        forced_outcome: str = "过牌",
    ) -> None:
        """写一条与怪物侧同构的决策记录（原因为占位句）。"""
        self._game.add_human_message(
            entity=entity,
            human_message=HumanMessage(
                content=build_combat_decision_record(
                    round_number,
                    action,
                    card_name=card_name,
                    targets=targets,
                    reason=REASON_PLACEHOLDER,
                    forced_cause=forced_cause,
                    forced_outcome=forced_outcome,
                ),
                combat_decision=build_combat_decision_tag(
                    round_number,
                    action,
                    card_name=card_name,
                    targets=targets,
                    reason=REASON_PLACEHOLDER,
                    forced=bool(forced_cause),
                ),
            ),
        )
