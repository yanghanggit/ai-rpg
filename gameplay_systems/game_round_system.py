from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from typing import final, override, Set
from game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from game.rpg_game import RPGGame
from components.components import (
    WorldComponent,
    ActorComponent,
    StageComponent,
    RoundEventsRecordComponent,
)
from models.event_models import GameRoundEvent
import gameplay_systems.prompt_utils


################################################################################################################################################
def _generate_game_round_prompt(game_round: int) -> str:
    return f"""# 提示: {gameplay_systems.prompt_utils.PromptTag.CURRENT_ROUND_TAG}:{game_round}"""


################################################################################################################################################
################################################################################################################################################
################################################################################################################################################


@final
class GameRoundSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        # 每次进入这个系统就增加一个回合
        self._game._runtime_round += 1
        logger.debug(f"_runtime_game_round = {self._game.current_round}")

        #
        self._dispatch_game_round_events()

        # 清除这个临时用的数据结构
        self._reset_round_event_records()

    ############################################################################################################
    def _dispatch_game_round_events(self) -> None:

        entities: Set[Entity] = self._context.get_group(
            Matcher(any_of=[WorldComponent, StageComponent, ActorComponent])
        ).entities

        # 移除上一回合的信息？
        # self.clear_previous_game_round_events(entities)

        self._context.notify_event(
            entities,
            GameRoundEvent(
                message=_generate_game_round_prompt(self._game.current_round)
            ),
        )

    ############################################################################################################
    # def clear_previous_game_round_events(self, entities: Set[Entity]) -> None:
    #     for entity in entities:
    #         safe_name = self._context.safe_get_entity_name(entity)
    #         retrieve_relevant_messages = self._context.agent_system.extract_messages_by_keywords(
    #             safe_name,
    #             set({gameplay_systems.prompt_utils.PromptTag.CURRENT_ROUND_TAG}),
    #         )
    #         self._context.agent_system.remove_excluded_messages(
    #             safe_name,
    #             retrieve_relevant_messages,
    #         )

    ############################################################################################################
    def _reset_round_event_records(self) -> None:

        entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[RoundEventsRecordComponent])
        ).entities

        for entity in entities:
            rounds_comp = entity.get(RoundEventsRecordComponent)
            entity.replace(RoundEventsRecordComponent, rounds_comp.name, [])

    ############################################################################################################


############################################################################################################
