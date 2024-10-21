from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import final, override, Any
from gameplay_systems.components import (
    PlayerComponent,
    DestroyComponent,
    ActorComponent,
    RPGAttributesComponent,
    ActorComponent,
)
from gameplay_systems.action_components import (
    DeadAction,
    ACTOR_INTERACTIVE_ACTIONS_REGISTER,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from typing import FrozenSet, Any


@final
class DeadActionSystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ########################################################################################################################################################################
    @override
    def execute(self) -> None:
        # 处理血量为0的情况
        self.handle_zero_hp_attributes()
        # 移除后续动作
        self.remove_actions(ACTOR_INTERACTIVE_ACTIONS_REGISTER)
        # 玩家死亡就游戏结束
        self.handle_player_dead()
        # 添加销毁
        self.add_destory()

    ########################################################################################################################################################################
    def handle_zero_hp_attributes(self) -> None:
        entities = self._context.get_group(
            Matcher(all_of=[RPGAttributesComponent], none_of=[DeadAction])
        ).entities
        for entity in entities:
            rpg_attributes = entity.get(RPGAttributesComponent)
            if rpg_attributes.hp <= 0:
                entity.add(DeadAction, rpg_attributes.name, [])

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
    def handle_player_dead(self) -> None:
        player_entities = self._context.get_group(
            Matcher(DeadAction, PlayerComponent)
        ).entities
        for player_entity in player_entities:
            player_comp = player_entity.get(PlayerComponent)
            player_proxy = self._game.get_player(player_comp.name)
            if player_proxy is None:
                assert False, f"没有找到玩家 = {player_comp.name}!!!!!!"
                continue
            player_proxy.on_dead()

    ########################################################################################################################################################################
    def add_destory(self) -> None:
        entities = self._context.get_group(Matcher(DeadAction)).entities
        for entity in entities:
            dead_caction = entity.get(DeadAction)
            if not entity.has(DestroyComponent):
                entity.add(DestroyComponent, dead_caction.name)


########################################################################################################################################################################
