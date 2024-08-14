from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from typing import override, List, Optional
from ecs_systems.components import StageComponent, ActorComponent, PlayerComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.stage_director_component import StageDirectorComponent, OnEnterStageComponent
from player.player_proxy import get_player_proxy
from ecs_systems.cn_builtin_prompt import stage_director_begin_prompt, stage_director_end_prompt, stage_director_event_wrap_prompt
from ecs_systems.stage_director_event import IStageDirectorEvent

class StageDirectorSystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        self._context: RPGEntitasContext = context
#################################################################################################################################################################
    @override
    def execute(self) -> None:
        self.handle()
        self.clear_director()
#################################################################################################################################################################
    def handle(self) -> None:
        entities = self._context.get_group(Matcher(all_of=[StageComponent, StageDirectorComponent])).entities
        for entity in entities:
            #logger.debug('=' *50)
            self.handle_stage(entity)
            #logger.debug('=' *50)
            self.handle_stage_actors(entity)
            #logger.debug('=' *50)
#################################################################################################################################################################   
    def clear_director(self) -> None:
        for entity in self._context.get_group(Matcher(all_of=[StageComponent, StageDirectorComponent])).entities:
            entity.get(StageDirectorComponent).clear()

        for entity in self._context.get_group(Matcher(all_of=[ActorComponent, OnEnterStageComponent])).entities.copy():
            entity.remove(OnEnterStageComponent)       
#################################################################################################################################################################
    def handle_stage(self, stage_entity: Entity) -> None:

        assert stage_entity.has(StageComponent)
        stage_comp = stage_entity.get(StageComponent)
        director_comp = stage_entity.get(StageDirectorComponent)
        
        events2stage = director_comp.to_stage(stage_comp.name, self._context)  
        for event in events2stage:
            logger.debug(f"handle_stage = {stage_comp.name}:{event}")
            self._context.safe_add_human_message_to_entity(stage_entity, event)       
#################################################################################################################################################################
    def handle_stage_actors(self, stage_entity: Entity) -> None:
        
        assert stage_entity.has(StageComponent)
        stage_comp = stage_entity.get(StageComponent)
        
        actors_int_this_stage = self._context.actors_in_stage(stage_comp.name)
        for actor_entity in actors_int_this_stage:
            if actor_entity.has(OnEnterStageComponent):
                # 新进入场景的人，不要收到这些事件。
                continue
            StageDirectorSystem.director_events_to_actor(self._context, actor_entity, None)
            StageDirectorSystem.director_events_to_player(self._context, actor_entity, None)
#################################################################################################################################################################
    @staticmethod
    def director_events_to_actor(context: RPGEntitasContext, actor_entity: Entity, input_stage_director_events: Optional[List[IStageDirectorEvent]]) -> None:
    
        stage_entity = context.safe_get_stage_entity(actor_entity)
        if stage_entity is None:
            return
        
        stage_director_comp = stage_entity.get(StageDirectorComponent)
        assert stage_director_comp is not None

        ### 添加消息！
        actor_comp = actor_entity.get(ActorComponent)

        events_2_actor: List[str] = []
        if input_stage_director_events is not None:
            events_2_actor = stage_director_comp._to_actor(actor_comp.name, context, input_stage_director_events)
        else:
            events_2_actor = stage_director_comp.to_actor(actor_comp.name, context)

        if len(events_2_actor) == 0:
            return

        ### 标记开始
        context.safe_add_human_message_to_entity(actor_entity, stage_director_begin_prompt(stage_director_comp.name, len(events_2_actor)))

        for index, event in enumerate(events_2_actor):
            prompt = stage_director_event_wrap_prompt(event, index)
            logger.debug(f"director_events_to_actor = {actor_comp.name}:{event}")
            context.safe_add_human_message_to_entity(actor_entity, prompt)

        ## 标记结束
        context.safe_add_human_message_to_entity(actor_entity, stage_director_end_prompt(stage_director_comp.name, len(events_2_actor)))
#################################################################################################################################################################
    @staticmethod
    def director_events_to_player(context: RPGEntitasContext, player_entity: Entity, input_stage_director_events: Optional[List[IStageDirectorEvent]]) -> None:

        if not player_entity.has(PlayerComponent) or not player_entity.has(ActorComponent):
            return

        stage_entity = context.safe_get_stage_entity(player_entity)
        if stage_entity is None:
            return
        
        player_comp = player_entity.get(PlayerComponent)
        player_name: str = player_comp.name
        player_proxy = get_player_proxy(player_name)
        if player_proxy is None:
            logger.error(f"notify_player_client, 玩家代理不存在{player_name}???")
            return
        
        stage_director_comp = stage_entity.get(StageDirectorComponent)
        assert stage_director_comp is not None

        ### 添加消息！
        actor_comp = player_entity.get(ActorComponent)

        events_2_player: List[str] = []
        if input_stage_director_events is not None:
            events_2_player = stage_director_comp._to_player(actor_comp.name, context, input_stage_director_events)
        else:
            events_2_player = stage_director_comp.to_player(actor_comp.name, context)

        for event_as_message in events_2_player:
            player_proxy.add_actor_message(actor_comp.name, event_as_message)
#################################################################################################################################################################
 
    