from overrides import override
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from ecs_systems.action_components import SpeakActionComponent, BroadcastActionComponent, WhisperActionComponent
from ecs_systems.components import PlayerComponent, ActorComponent
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from ecs_systems.stage_director_component import StageDirectorComponent
from typing import List, Set, Optional, Dict
from my_agent.lang_serve_agent_system import LangServeAgentSystem
from builtin_prompt.cn_builtin_prompt import batch_conversation_action_events_in_stage_prompt
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask, LangServeAgentAsyncRequestTasksGather

# 这个类就是故意打包将对话类事件先进行一次request，如果LLM发现有政策问题就会抛异常，不会将污染的message加入chat history，这样就不可能进入chat_history。
# 这么做是防止玩家的对话内容包含了非法信息和违反政策的内容。
####################################################################################################
class PostConversationActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self._context = context
        self._async_execute: bool = True
        self._request_tasks: Dict[str, LangServeAgentRequestTask] = {}
####################################################################################################
    @override 
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(any_of=[SpeakActionComponent, BroadcastActionComponent, WhisperActionComponent]): GroupEvent.ADDED}
####################################################################################################
    @override 
    def filter(self, entity: Entity) -> bool:
        # 如果去掉entity.has(PlayerComponent)。就是处理所有的Actor的对话事件，最保险的做法。
        # 有PlayerComponent就节省一些
        return entity.has(PlayerComponent) and entity.has(ActorComponent)
####################################################################################################
    @override 
    def react(self, entities: list[Entity]) -> None:

        ## 所有场景，发生了任何对话的事件
        stage_entities: Set[Entity] = set()
        for entity in entities:
            stage_entity = self.collect_stage(entity)
            if stage_entity is not None:
                stage_entities.add(stage_entity)

        self._request_tasks.clear()
        for stage_entity in stage_entities:
            self.before_handle(stage_entity)
            self.handle(stage_entity, self._async_execute, self._request_tasks)
            self.after_handle(stage_entity)
####################################################################################################   
    def before_handle(self, stage_entity: Entity) -> None:
        assert stage_entity.has(StageDirectorComponent)
        safename = self._context.safe_get_entity_name(stage_entity)
        logger.warning(f"? {safename}:这里可以写，如果你说出来的话包涵了你目前不该知道的信息，就可以关掉。例如用broadcast喊某个地点，然后就能去了之类的")
####################################################################################################
    def after_handle(self, stage_entity: Entity) -> None:
        assert stage_entity.has(StageDirectorComponent)
        stage_director_comp: StageDirectorComponent = stage_entity.get(StageDirectorComponent)
        stage_director_comp.clear()
####################################################################################################
    def collect_stage(self, entity: Entity) -> Optional[Entity]:
        stage_entity = self._context.safe_get_stage_entity(entity)
        return stage_entity
####################################################################################################
    def handle(self, stage_entity: Entity, async_execute: bool, request_tasks: Dict[str, LangServeAgentRequestTask]) -> None:
        stage_director_comp: StageDirectorComponent = stage_entity.get(StageDirectorComponent)
        if len(stage_director_comp._events) == 0:
            return
        ##
        #处理场景的
        raw_events2stage = stage_director_comp.to_stage(stage_director_comp.name, self._context) 
        if len(raw_events2stage) > 0:
            batch_events2stage_prompt = self.batch_stage_events(stage_director_comp.name, raw_events2stage) 
            logger.info(f"PostConversationActionSystem: {stage_director_comp.name} : {batch_events2stage_prompt}")
            if async_execute:
                task = self._context._langserve_agent_system.create_agent_request_task_for_checking_prompt(stage_director_comp.name, batch_events2stage_prompt)
                assert task is not None
                request_tasks[stage_director_comp.name] = task
            else:
                self.imme_request(stage_director_comp.name, batch_events2stage_prompt)

        ### 处理Actor的
        actors_in_this_stage = self._context.actors_in_stage(stage_director_comp.name)
        for _entity in actors_in_this_stage:
            actor_comp: ActorComponent = _entity.get(ActorComponent)
            raw_events2actor = stage_director_comp.to_actor(actor_comp.name, self._context)     
            if len(raw_events2actor) > 0:
                batch_events2actor_prompt = self.batch_actor_events(stage_director_comp.name, raw_events2actor)
                logger.info(f"PostConversationActionSystem: {actor_comp.name} : {batch_events2actor_prompt}")
                if async_execute:
                    task = self._context._langserve_agent_system.create_agent_request_task_for_checking_prompt(actor_comp.name, batch_events2actor_prompt)
                    assert task is not None
                    request_tasks[actor_comp.name] = task
                else:
                    self.imme_request(actor_comp.name, batch_events2actor_prompt)
####################################################################################################
    def imme_request(self, name: str, prompt: str) -> None:
        try:
            agent_request = self._context._langserve_agent_system.create_agent_request_task_for_checking_prompt(name, prompt)
            if agent_request is None:
                logger.error(f"imme_request: {name} request error.")
                return
            
            response = agent_request.request()
            if response is None:
                logger.error(f"imme_request: {name} request error.")
        except Exception as e:
                logger.error(f"imme_request: {name} request error.")
####################################################################################################
    def batch_stage_events(self, stagename: str, events2stage: List[str]) -> str:
        return batch_conversation_action_events_in_stage_prompt(stagename, events2stage)
####################################################################################################
    def batch_actor_events(self, stagename: str, events2actor: List[str]) -> str:
        return batch_conversation_action_events_in_stage_prompt(stagename, events2actor)
####################################################################################################
    async def async_post_execute(self) -> None:
        # 并行执行requests
        if len(self._request_tasks) == 0:
            return
        logger.debug(f"PostConversationActionSystem async_post_execute begin.")     
        tasks_gather = LangServeAgentAsyncRequestTasksGather("PostConversationActionSystem Gather", self._request_tasks)
        request_result = await tasks_gather.gather()
        if len(request_result) == 0:
            logger.warning(f"PostConversationActionSystem: request_result is empty.")
            return
    
        #正常流程
        for name, task in self._request_tasks.items():
            if task is None:
                logger.error(f"PostConversationActionSystem: {name} response is None or empty.")
            else:
                # AI的回复不要，防止污染上下文
                logger.debug(f"PostConversationActionSystem: {name} response is {task.response_content}")

        logger.debug(f"PostConversationActionSystem async_post_execute end.")
####################################################################################################
