from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from typing import final, override, Set
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from rpg_game.rpg_game import RPGGame
from my_components.components import (
    WorldComponent,
    ActorComponent,
    StageComponent,
    RoundEventsRecordComponent,
)
from my_models.event_models import GameRoundEvent


################################################################################################################################################
def _generate_game_round_prompt(game_round: int) -> str:
    return f"""# 提示: 当前回合数: {game_round}"""


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

        self._context.notify_event(
            entities,
            GameRoundEvent(
                message=_generate_game_round_prompt(self._game.current_round)
            ),
        )

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
