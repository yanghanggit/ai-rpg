from typing import override
from entitas import Matcher, ExecuteProcessor, Entity #type: ignore
from ecs_systems.components import (PlayerComponent, DestroyComponent)
from ecs_systems.action_components import DeadActionComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from my_agent.agent_action import AgentAction
from rpg_game.rpg_game import RPGGame
from typing import Set

class DeadActionSystem(ExecuteProcessor):
    
########################################################################################################################################################################
    def __init__(self, context: RPGEntitasContext, rpggame: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._rpggame: RPGGame = rpggame
########################################################################################################################################################################
    @override
    def execute(self) -> None:
        # 玩家死亡就游戏结束
        self.is_player_dead_then_game_over()
        # 销毁
        self.destory()
########################################################################################################################################################################
    def is_player_dead_then_game_over(self) -> None:
        entities: Set[Entity] = self._context.get_group(Matcher(DeadActionComponent)).entities
        for entity in entities:
            if entity.has(PlayerComponent):
                logger.warning(f"玩家死亡，游戏结束")
                self._rpggame.exited = True
                self._rpggame.on_exit()
########################################################################################################################################################################  
    def destory(self) -> None:
        entities: Set[Entity] = self._context.get_group(Matcher(DeadActionComponent)).entities
        for entity in entities:
            dead_comp = entity.get(DeadActionComponent)
            action: AgentAction = dead_comp.action
            if not entity.has(DestroyComponent):
                entity.add(DestroyComponent, action._actor_name) ### 这里只需要名字，不需要values，谁造成了你的死亡
########################################################################################################################################################################
            

        
             
            
        


    