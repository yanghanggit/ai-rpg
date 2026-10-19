"""出牌前系统（队员）：为已发生的出牌 / 过牌写一条决策记录，形状与怪物侧一致。

队员的决策来自玩家，计算端没有决策推理，所以只落记录不推理；原因用占位句留白。
"""

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
)


#######################################################################################################################################
@final
class PartyPrePlaySystem(ReactiveProcessor):
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
            logger.debug("PartyPrePlaySystem: 战斗未进行中，跳过")
            return

        round_number = len(self._game.current_dungeon_combat_room.combat.rounds or [])

        for entity in entities:
            if entity.has(PlayCardsAction):
                self._record_play(entity, round_number)
            else:
                self._record_pass(entity, round_number)

    #######################################################################################################################################
    def _record_play(self, entity: Entity, round_number: int) -> None:
        action = entity.get(PlayCardsAction)
        card_name = action.card.name
        targets = list(action.targets)

        self._write(entity, round_number, ACTION_PLAY, card_name, targets)
        logger.debug(
            f"PartyPrePlaySystem: [{entity.name}] 记录出牌决策 '{card_name}'，目标：{targets}"
        )

    #######################################################################################################################################
    def _record_pass(self, entity: Entity, round_number: int) -> None:
        self._write(entity, round_number, ACTION_PASS, "", [])
        logger.debug(f"PartyPrePlaySystem: [{entity.name}] 记录过牌决策")

    #######################################################################################################################################
    def _write(
        self,
        entity: Entity,
        round_number: int,
        action: str,
        card_name: str,
        targets: List[str],
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
                ),
                combat_decision=build_combat_decision_tag(
                    round_number,
                    action,
                    card_name=card_name,
                    targets=targets,
                    reason=REASON_PLACEHOLDER,
                    forced=False,
                ),
            ),
        )
