from loguru import logger
from entitas import InitializeProcessor, ExecuteProcessor, Matcher  # type: ignore
from overrides import override
from typing import cast, final, Set
from entitas import Entity  # type: ignore
from game.tcg_game import TCGGame
from game.tcg_game_context import TCGGameContext
from components.components import (
    ActorComponent,
    ActorRolePlayPlanningPermitFlagComponent,
)


#######################################################################################################################################
@final
class ActorRoleplayPlanningPermitSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        # 实现交叉对话，后续找个更优雅的逻辑 TODO
        self.counter: int = 0
        assert self._game is not None

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        player_entity = self._game.get_player_entity()
        assert player_entity is not None
        player_stage = self._context.safe_get_stage_entity(player_entity)
        if player_stage is None:
            logger.error("Player stage is None")
            return
        # 得到所有在玩家所在stage的actor
        actors = list(self._context.retrieve_stage_actor_mapping()[player_stage])
        if len(actors) == 0:
            return
        # player不需要让ai思考
        # actors.remove(player_entity) TODO 测试

        # 轮到的人才能说话
        talker_num = self.counter % len(actors)
        self.counter += 1
        self._add_permit({actors[talker_num]})

    #######################################################################################################################################
    def _add_permit(self, entities: Set[Entity]) -> None:
        for entity in entities:
            entity.replace(
                ActorRolePlayPlanningPermitFlagComponent,
                entity.get(ActorComponent).name,
            )
