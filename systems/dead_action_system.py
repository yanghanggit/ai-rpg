
from typing import override
from entitas import Matcher, ExecuteProcessor, Entity #type: ignore
from auxiliary.components import (DeadActionComponent, PlayerComponent,
                        DestroyComponent)
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from actor_plan_and_action.actor_action import ActorAction
from rpg_game import RPGGame
from typing import Set

class DeadActionSystem(ExecuteProcessor):
    
########################################################################################################################################################################
    def __init__(self, context: ExtendedContext, rpggame: RPGGame) -> None:
        self.context = context
        self.rpggame = rpggame
########################################################################################################################################################################
    @override
    def execute(self) -> None:
        # 玩家死亡就游戏结束
        self.is_player_dead_then_game_over()
        # 销毁
        self.destory()
########################################################################################################################################################################
    def is_player_dead_then_game_over(self) -> None:
        entities: Set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
        for entity in entities:
            if entity.has(PlayerComponent):
                logger.warning(f"玩家死亡，游戏结束")
                self.rpggame.exited = True
                self.rpggame.on_exit()
########################################################################################################################################################################  
    def destory(self) -> None:
        entities: Set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
        for entity in entities:
            deadcomp: DeadActionComponent = entity.get(DeadActionComponent)
            action: ActorAction = deadcomp.action
            if not entity.has(DestroyComponent):
                entity.add(DestroyComponent, action._actor_name) ### 这里只需要名字，不需要values，谁造成了你的死亡
########################################################################################################################################################################
            

        
             
            
        


    