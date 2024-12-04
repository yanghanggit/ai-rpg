from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import final, override, Any
from components.components import (
    PlayerComponent,
    DestroyComponent,
    ActorComponent,
    AttributesComponent,
    ActorComponent,
)
from components.actions import (
    DeadAction,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
)
from game.rpg_game_context import RPGGameContext
from game.rpg_game import RPGGame
from typing import FrozenSet, Any
from loguru import logger


@final
class DeadActionSystem(ExecuteProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ########################################################################################################################################################################
    @override
    def execute(self) -> None:
        # 处理血量为0的情况
        self._update_entities_to_dead_state()
        # 移除后续动作
        self._clear_actions(ACTOR_AVAILABLE_ACTIONS_REGISTER)
        # 玩家死亡就游戏结束
        self._process_player_death()
        # 添加销毁
        self._add_destory()

    ########################################################################################################################################################################
    def _update_entities_to_dead_state(self) -> None:
        entities = self._context.get_group(
            Matcher(all_of=[AttributesComponent], none_of=[DeadAction])
        ).entities
        for entity in entities:
            rpg_attributes = entity.get(AttributesComponent)
            if rpg_attributes.cur_hp <= 0:
                entity.add(DeadAction, rpg_attributes.name, [])

    ########################################################################################################################################################################
    def _clear_actions(self, action_comps: FrozenSet[type[Any]]) -> None:
        actor_entities = self._context.get_group(
            Matcher(
                all_of=[ActorComponent, DeadAction],
                any_of=action_comps,
            )
        ).entities.copy()

        for entity in actor_entities:
            for action_class in action_comps:
                if action_class == DeadAction:
                    # 死亡动作不移除。
                    continue

                if entity.has(action_class):
                    entity.remove(action_class)

    ########################################################################################################################################################################
    def _process_player_death(self) -> None:
        player_entities = self._context.get_group(
            Matcher(DeadAction, PlayerComponent)
        ).entities
        for player_entity in player_entities:
            player_comp = player_entity.get(PlayerComponent)
            player_proxy = self._game.get_player(player_comp.name)
            if player_proxy is None:
                logger.error(f"player {player_comp.name} not found")
                continue
            player_proxy.on_dead()

    ########################################################################################################################################################################
    def _add_destory(self) -> None:
        entities = self._context.get_group(Matcher(DeadAction)).entities
        for entity in entities:
            dead_caction = entity.get(DeadAction)
            entity.replace(DestroyComponent, dead_caction.name)


########################################################################################################################################################################
