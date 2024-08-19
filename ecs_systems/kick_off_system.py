from entitas import Entity, Matcher, InitializeProcessor, ExecuteProcessor # type: ignore
from overrides import override
from ecs_systems.components import WorldComponent, StageComponent, ActorComponent, PlayerComponent
from ecs_systems.action_components import PerceptionAction, CheckStatusAction
import ecs_systems.cn_builtin_prompt as builtin_prompt
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, Set, List
from my_agent.agent_action import AgentAction
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask, LangServeAgentAsyncRequestTasksGather
from rpg_game.rpg_game import RPGGame 
from file_system.files_def import PropFile

######################################################################################################################################################
class KickOffSystem(InitializeProcessor, ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._tasks: Dict[str, LangServeAgentRequestTask] = {}
        self._once_add_perception_and_check_status: bool = False
        self._rpg_game: RPGGame = rpg_game
######################################################################################################################################################
    @override
    def initialize(self) -> None:
        #分段处理
        self._tasks.clear()
        world_tasks = self.create_world_system_tasks()
        stage_tasks = self.create_stage_tasks()
        actor_tasks = self.create_actor_tasks()
        self.handle_players()
        #填进去
        self._tasks.update(world_tasks)
        self._tasks.update(stage_tasks)
        self._tasks.update(actor_tasks)
######################################################################################################################################################
    @override
    def execute(self) -> None:
        if not self._once_add_perception_and_check_status:
            self._once_add_perception_and_check_status = True
            self.once_add_perception_and_check_status()
######################################################################################################################################################
    def once_add_perception_and_check_status(self) -> None:
        actor_entities = self._context.get_group(Matcher(all_of=[ActorComponent], none_of=[PlayerComponent])).entities
        for actor_entity in actor_entities:
        
            actor_comp = actor_entity.get(ActorComponent)
        
            if not actor_entity.has(PerceptionAction):
                actor_entity.add(PerceptionAction, AgentAction(actor_comp.name, PerceptionAction.__name__, [actor_comp.current_stage]))
        
            if not actor_entity.has(CheckStatusAction):
                actor_entity.add(CheckStatusAction, AgentAction(actor_comp.name, CheckStatusAction.__name__, [actor_comp.name]))
######################################################################################################################################################
    @override
    async def async_pre_execute(self) -> None:

        if len(self._tasks) == 0:
            return

        gather = LangServeAgentAsyncRequestTasksGather("AgentsKickOffSystem", self._tasks)
        response = await gather.gather()
        if len(response) == 0:
            logger.warning(f"AgentsKickOffSystem: request_result is empty.")
            return

        self._tasks.clear() # 这句必须得走.
######################################################################################################################################################
    def create_world_system_tasks(self) -> Dict[str, LangServeAgentRequestTask]:

        ret: Dict[str, LangServeAgentRequestTask] = {}
    
        world_entities: Set[Entity] = self._context.get_group(Matcher(WorldComponent)).entities
        for world_entity in world_entities:

            world_comp = world_entity.get(WorldComponent)
            agent = self._context._langserve_agent_system.get_agent(world_comp.name)
            if agent is None:
                continue
            
            task = LangServeAgentRequestTask.create(agent, builtin_prompt.kick_off_world_system_prompt(self._rpg_game.about_game))
            if task is not None:
                ret[world_comp.name] = task
        
        return ret
######################################################################################################################################################
    def create_stage_tasks(self) -> Dict[str, LangServeAgentRequestTask]:

        ret: Dict[str, LangServeAgentRequestTask] = {}
       
        stage_entities: Set[Entity] = self._context.get_group(Matcher(StageComponent)).entities
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            agent = self._context._langserve_agent_system.get_agent(stage_comp.name)
            if agent is None:
                continue

            kick_off_message = self._context._kick_off_message_system.get_message(stage_comp.name)
            if kick_off_message == "":
                continue
            

            kick_off_prompt = builtin_prompt.kick_off_stage_prompt(kick_off_message, 
                                                    self._rpg_game.about_game, 
                                                    self.get_props_in_stage(stage_entity), 
                                                    self.get_actor_names_in_stage(stage_entity))
            

            task = LangServeAgentRequestTask.create(agent, kick_off_prompt)
            if task is not None:
                ret[stage_comp.name] = task
        
        return ret
######################################################################################################################################################
    def create_actor_tasks(self) -> Dict[str, LangServeAgentRequestTask]:

        ret: Dict[str, LangServeAgentRequestTask] = {}
     
        actor_entities: Set[Entity] = self._context.get_group(Matcher(all_of=[ActorComponent], none_of=[PlayerComponent] )).entities
        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            agent = self._context._langserve_agent_system.get_agent(actor_comp.name)
            if agent is None:
                continue

            kick_off_message = self._context._kick_off_message_system.get_message(actor_comp.name)
            if kick_off_message == "":
                logger.error(f"kick_off_message is empty: {actor_comp.name}")
                continue
            
            task = LangServeAgentRequestTask.create(agent, builtin_prompt.kick_off_actor_prompt(kick_off_message, self._rpg_game.about_game))
            if task is not None:
                ret[actor_comp.name] = task
           
        return ret
######################################################################################################################################################
    def handle_players(self) -> None:
        actor_entities = self._context.get_group(Matcher( all_of = [ActorComponent, PlayerComponent])).entities
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            kick_off_message = self._context._kick_off_message_system.get_message(actor_comp.name)
            if kick_off_message == "":
                logger.error(f"kick_off_message is empty: {actor_comp.name}")
                continue
            prompt = builtin_prompt.kick_off_actor_prompt(kick_off_message, self._rpg_game.about_game)
            self._context.safe_add_human_message_to_entity(actor_entity, prompt)
######################################################################################################################################################
    def get_actor_names_in_stage(self, entity: Entity) -> Set[str]:
        stage_comp = entity.get(StageComponent)
        actors_in_stage = self._context.actors_in_stage(stage_comp.name)
        ret: Set[str] = set()
        for actor_entity in actors_in_stage:
            actor_comp = actor_entity.get(ActorComponent)
            ret.add(actor_comp.name)
        return ret
######################################################################################################################################################
    def get_props_in_stage(self, entity: Entity) -> List[PropFile]:
        safe_stage_name = self._context.safe_get_entity_name(entity)
        return self._context._file_system.get_files(PropFile, safe_stage_name)
######################################################################################################################################################
