from math import log
from typing import List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher
from .base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    DirectorAction,
    HandComponent,
    PlayCardsAction,
    # TurnAction,
)


#######################################################################################################################################
@final
class PlayCardsActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction) and entity.has(HandComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        if len(entities) == 0:
            return

        if not self._game.current_engagement.is_on_going_phase:
            return

        assert self._game.current_engagement.is_on_going_phase
        await self._handle_actions(entities)

    #######################################################################################################################################
    async def _handle_actions(self, react_entities: List[Entity]) -> None:
        # 处理场景
        current_stage = self._game.safe_get_stage_entity(react_entities[0])
        assert current_stage is not None
        assert not current_stage.has(DirectorAction)
        current_stage.replace(
            DirectorAction,
            current_stage._name,
            "",
            "",
        )
        logger.debug(
            f"PlayCardsActionSystem: stage_entity: {current_stage._name}, react_entities: {[entity._name for entity in react_entities]}"
        )

        # # 处理角色
        for actor_entity in react_entities:
            #
            assert actor_entity.has(HandComponent)
            assert actor_entity.has(PlayCardsAction)
            logger.debug(
                f"actor_entity: {actor_entity._name}, play_cards_action: {actor_entity.get(PlayCardsAction).model_dump_json()}"
            )

            # hand_comp = actor_entity.get(HandComponent)
            # turn_action = actor_entity.get(TurnAction)

            # skill = hand_comp.get_skill(turn_action.skill)
            # detail = hand_comp.get_action_detail(turn_action.skill)
            # assert skill.name != "", f"技能名称错误: {actor_entity._name}"
            # assert (
            #     detail.skill != "" and detail.skill == skill.name
            # ), f"技能名称错误: {actor_entity._name}"

            # # 给角色添加！！！
            # assert not actor_entity.has(PlayCardsAction)
            # actor_entity.replace(
            #     PlayCardsAction,
            #     actor_entity._name,
            #     # detail.targets,
            #     skill,
            #     detail.dialogue,
            #     detail.reason,
            # )

            # logger.debug(
            #     f"actor_entity: {actor_entity._name}, skill: {skill.name}, reason: {detail.reason}, dialogue: {detail.dialogue}"
            # )

    #######################################################################################################################################
