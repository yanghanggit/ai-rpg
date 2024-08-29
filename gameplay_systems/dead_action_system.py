from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import override, List, Any
from gameplay_systems.components import (
    PlayerComponent,
    DestroyComponent,
    ActorComponent,
)
from gameplay_systems.action_components import (
    DeadAction,
    ACTOR_INTERACTIVE_ACTIONS_REGISTER,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from rpg_game.rpg_game import RPGGame
from typing import FrozenSet, Any


class DeadActionSystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ########################################################################################################################################################################
    @override
    def execute(self) -> None:
        # 移除后续动作
        self.remove_actions(ACTOR_INTERACTIVE_ACTIONS_REGISTER)
        # 玩家死亡就游戏结束
        self.is_player_dead_then_game_over()
        # 添加销毁
        self.add_destory()

    ########################################################################################################################################################################
    def remove_actions(self, action_comps: FrozenSet[type[Any]]) -> None:
        actor_entities = self._context.get_group(
            Matcher(
                all_of=[ActorComponent, DeadAction],
                any_of=action_comps,
            )
        ).entities.copy()

        for entity in actor_entities:
            for action_class in action_comps:
                if entity.has(action_class):
                    entity.remove(action_class)

    ########################################################################################################################################################################
    def is_player_dead_then_game_over(self) -> None:
        entities = self._context.get_group(Matcher(DeadAction)).entities
        for entity in entities:
            if entity.has(PlayerComponent):
                logger.warning(f"玩家死亡，游戏结束")
                self._game.exited = True
                self._game.on_exit()

    ########################################################################################################################################################################
    def add_destory(self) -> None:
        entities = self._context.get_group(Matcher(DeadAction)).entities
        for entity in entities:
            dead_caction = entity.get(DeadAction)
            if not entity.has(DestroyComponent):
                entity.add(DestroyComponent, dead_caction.name)


########################################################################################################################################################################
