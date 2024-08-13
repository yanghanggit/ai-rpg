from entitas import Matcher, ExecuteProcessor #type: ignore
from typing import override
from ecs_systems.components import PlayerComponent, DestroyComponent, ActorComponent
from ecs_systems.action_components import DeadAction, ACTOR_INTERACTIVE_ACTIONS_REGISTER
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from my_agent.agent_action import AgentAction
from rpg_game.rpg_game import RPGGame

class DeadActionSystem(ExecuteProcessor):
    

    def __init__(self, context: RPGEntitasContext, rpggame: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._rpg_game: RPGGame = rpggame
########################################################################################################################################################################
    @override
    def execute(self) -> None:
        # 移除后续动作
        self.remove_interactive_actions()
        # 玩家死亡就游戏结束
        self.is_player_dead_then_game_over()
        # 添加销毁
        self.add_destory()
########################################################################################################################################################################
    def remove_interactive_actions(self) -> None:
        actor_entities = self._context.get_group(Matcher(all_of = [ActorComponent, DeadAction], any_of = ACTOR_INTERACTIVE_ACTIONS_REGISTER)).entities.copy()
        for entity in actor_entities:
            for action_class in ACTOR_INTERACTIVE_ACTIONS_REGISTER:
                if entity.has(action_class):
                    entity.remove(action_class)
########################################################################################################################################################################
    def is_player_dead_then_game_over(self) -> None:
        entities = self._context.get_group(Matcher(DeadAction)).entities
        for entity in entities:
            if entity.has(PlayerComponent):
                logger.warning(f"玩家死亡，游戏结束")
                self._rpg_game.exited = True
                self._rpg_game.on_exit()
########################################################################################################################################################################  
    def add_destory(self) -> None:
        entities = self._context.get_group(Matcher(DeadAction)).entities
        for entity in entities:
            dead_comp = entity.get(DeadAction)
            action: AgentAction = dead_comp.action
            if not entity.has(DestroyComponent):
                entity.add(DestroyComponent, action._actor_name) ### 这里只需要名字，不需要values，谁造成了你的死亡
########################################################################################################################################################################
            

        
             
            
        


    