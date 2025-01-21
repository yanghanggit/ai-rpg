from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import final, override
from game.rpg_game_context import RPGGameContext
from components.actions import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
)
import rpg_game_systems.action_component_utils
from game.rpg_game import RPGGame
from components.components import SkillComponent, DestroyComponent


@final
class PostActionSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        self._remove_all_actions()
        self._remove_all_skills()

    ############################################################################################################
    def _remove_all_actions(self) -> None:
        rpg_game_systems.action_component_utils.clear_registered_actions(
            self._context,
            (ACTOR_AVAILABLE_ACTIONS_REGISTER | STAGE_AVAILABLE_ACTIONS_REGISTER),
        )
        self._test()

    ############################################################################################################
    # todo
    def _remove_all_skills(self) -> None:
        skill_entities = self._context.get_group(
            Matcher(all_of=[SkillComponent], none_of=[DestroyComponent])
        ).entities.copy()
        for skill_entity in skill_entities:
            skill_entity.replace(DestroyComponent, "")

    ############################################################################################################
    def _test(self) -> None:
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
