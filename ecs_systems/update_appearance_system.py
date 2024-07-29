from overrides import override
from entitas import Entity, InitializeProcessor, ExecuteProcessor, Matcher # type: ignore
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from typing import Dict, cast, Set
from my_agent.lang_serve_agent_system import LangServeAgentSystem
import json
from ecs_systems.components import AppearanceComponent, BodyComponent, ActorComponent
from builtin_prompt.cn_builtin_prompt import actors_body_and_clothe_prompt

# todo
class UpdateAppearanceSystem(InitializeProcessor, ExecuteProcessor):

    """
    更新外观信息的系统
    """

    def __init__(self, context: ExtendedContext, system_name: str) -> None:
        self._context: ExtendedContext = context
        self._system_name: str = str(system_name)
        assert self._system_name == "角色外观生成器"
        assert len(self._system_name) > 0
###############################################################################################################################################
    @override
    def initialize(self) -> None:
        pass
###############################################################################################################################################
    @override
    def execute(self) -> None:
        context = self._context
        world_entity = context.get_world_entity(self._system_name)
        if world_entity is None:
            # 没有这个对象，就认为这个系统不成立。
            logger.warning(f"{self._system_name}, world_entity is None.")
            return
        self._execute(world_entity)
###############################################################################################################################################
    def _execute(self, world_entity: Entity) -> None:
        assert world_entity is not None
        actors_body_and_clothe = self.get_actors_body_and_clothe()
        if len(actors_body_and_clothe) == 0:
            return        
        logger.warning(f"这是一个测试的系统，正在运行。")
        # 没有衣服的，直接更新外观
        self.imme_update_appearance(actors_body_and_clothe)
        # 有衣服的，请求更新，通过LLM来推理外观
        self.request_update_appearance(actors_body_and_clothe, world_entity)
###############################################################################################################################################
    # 没有衣服的，就直接更新外观，一般是动物类的，或者非人类的。
    def imme_update_appearance(self, actors_body_and_clothe:  Dict[str, tuple[str, str]]) -> None:
        context = self._context
        for name, (body, clothe) in actors_body_and_clothe.items():
            if clothe == "" and body != "":
                entity = context.get_actor_entity(name)
                assert entity is not None
                assert entity.has(AppearanceComponent)
                assert entity.has(BodyComponent)
                body = self.get_body(entity)
                assert body != ""
                hash_code = hash(body)
                entity.replace(AppearanceComponent, body, hash_code)
                logger.debug(f"{name}, update_appearance_by_body: {body}")
###############################################################################################################################################
    # 有衣服的，请求更新，通过LLM来推理外观。
    def request_update_appearance(self, actors_body_and_clothe:  Dict[str, tuple[str, str]], world_entity: Entity) -> bool:
        assert world_entity is not None
        final_prompt = actors_body_and_clothe_prompt(actors_body_and_clothe)
        if final_prompt == "":
            logger.error(f"final_prompt is empty.")
            return False

        logger.debug(f"final_prompt: {final_prompt}")

        # 请求更新
        safe_name = self._context.safe_get_entity_name(world_entity)
        try:

            agent_request = self._context._langserve_agent_system.create_agent_request_task_without_any_context(safe_name, final_prompt)
            if agent_request is None:
                logger.error(f"{safe_name} request error.")
                return False

            #
            response = agent_request.request()
            # 注意 DO_NOT_ADD_MESSAGE_TO_CHAT_HISTORY，不要把这个消息加入到聊天记录中。因为世界级系统不需要存储上下文。
            #response = langserve_agent_system.agent_request(safe_name, final_prompt, AddChatHistoryOptionOnRequestSuccess.NOT_ADD_ANY_TO_CHAT_HISTORY)
            if response is None:
                logger.error(f"{safe_name} request response is None.")
                return False
            
            json_response: Dict[str, str] = json.loads(response)
            self.on_request_success(json_response)

        except Exception as e:
            logger.error(f"{safe_name} request error = {e}")
            return False
        return True
###############################################################################################################################################
    # 请求成功后的处理，就是把AppearanceComponent 设置一遍
    def on_request_success(self, json_response: Dict[str, str]) -> None:
        context = self._context
        for name, appearance in json_response.items():
            entity = context.get_actor_entity(name)
            if entity is None:
                logger.error(f"update_after_requst, entity is None, name: {name}")
                continue
            hash_code = hash(appearance)
            entity.replace(AppearanceComponent, appearance, hash_code)
            logger.debug(f"{name}, update_after_requst: {appearance}")
###############################################################################################################################################
    # 获取所有的角色的身体和衣服
    def get_actors_body_and_clothe(self) -> Dict[str, tuple[str, str]]:
        res: Dict[str, tuple[str, str]] = {}
        actors: Set[Entity] = self._context.get_group(Matcher(all_of = [AppearanceComponent, BodyComponent, ActorComponent])).entities
        for _actor in actors:
            appearance_comp = _actor.get(AppearanceComponent)
            if appearance_comp.appearance != "":
                continue
            name = cast(ActorComponent, _actor.get(ActorComponent)).name
            body = self.get_body(_actor)
            clothe = self.get_clothe(_actor)
            logger.debug(f"actor: {name}, body: {body}, clothe: {clothe}")
            res[name] = (body, clothe)
        return res
###############################################################################################################################################
    # 获取衣服的描述 todo。现在就返回了第一个衣服的描述
    def get_clothe(self, entity: Entity) -> str:
        safename = self._context.safe_get_entity_name(entity)            
        files = self._context._file_system.get_prop_files(safename)
        for _file in files:
            if _file._prop.is_clothes():
                return _file._prop._description
        return "" 
###############################################################################################################################################
    # 获取身体的描述。
    def get_body(self, entity: Entity) -> str:
        if not entity.has(BodyComponent):
            return ""
        body_comp: BodyComponent = entity.get(BodyComponent)
        return cast(str, body_comp.body)
###############################################################################################################################################
   
