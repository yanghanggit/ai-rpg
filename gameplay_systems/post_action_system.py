from typing import override
from entitas import ExecuteProcessor, Matcher  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from gameplay_systems.components import StageComponent, ActorComponent
from gameplay_systems.action_components import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
)
import gameplay_systems.planning_helper


class PostActionSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: RPGEntitasContext) -> None:
        self._context: RPGEntitasContext = context

    ############################################################################################################
    @override
    def execute(self) -> None:
        # 在这里清除所有的行动
        all_actions_register = (
            ACTOR_AVAILABLE_ACTIONS_REGISTER + STAGE_AVAILABLE_ACTIONS_REGISTER
        )
        gameplay_systems.planning_helper.remove_all(self._context, all_actions_register)
        self.test()

    ############################################################################################################
    def test(self) -> None:
        stage_entities = self._context.get_group(
            Matcher(any_of=STAGE_AVAILABLE_ACTIONS_REGISTER)
        ).entities
        assert (
            len(stage_entities) == 0
        ), f"Stage entities with actions: {stage_entities}"
        actor_entities = self._context.get_group(
            Matcher(any_of=ACTOR_AVAILABLE_ACTIONS_REGISTER)
        ).entities
        assert (
            len(actor_entities) == 0
        ), f"Actor entities with actions: {actor_entities}"


############################################################################################################
