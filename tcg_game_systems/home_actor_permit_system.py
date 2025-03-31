from entitas import ExecuteProcessor, Entity  # type: ignore
from overrides import override
from typing import final, Set
from game.tcg_game import TCGGame
from components.components_v_0_0_1 import (
    ActorComponent,
    ActorPermitComponent,
)
from loguru import logger


#######################################################################################################################################
@final
class HomeActorPermitSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        self._assign_actor_permits()

    #######################################################################################################################################
    def _assign_actor_permits(self) -> None:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        actors_on_stage = self._game.retrieve_actors_on_stage(player_entity)

        # 获取目前有 ActorPermitComponent 的actor
        permit_actors: Set[Entity] = set()
        for actor in actors_on_stage:
            if actor.has(ActorPermitComponent):
                permit_actors.add(actor)
                logger.debug(
                    f"HomeActorPermitSystem: ActorPermitComponent: {actor.get(ActorPermitComponent).name}，已经有 ActorPermitComponent。"
                )
            else:
                logger.debug(
                    f"HomeActorPermitSystem: ActorPermitComponent: {actor.get(ActorComponent).name}，没有 ActorPermitComponent。"
                )

        # 如果没有 ActorPermitComponent 的actor，给所有的actor添加 ActorPermitComponent
        if len(permit_actors) == 0:
            # 如果清空了，就刷新一遍给所有的actor添加 ActorPermitComponent
            permit_actors = actors_on_stage
            for actor in permit_actors:
                actor.replace(
                    ActorPermitComponent,
                    actor._name,
                )
    #######################################################################################################################################
