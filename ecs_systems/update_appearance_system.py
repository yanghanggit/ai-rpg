from entitas import Entity, InitializeProcessor, ExecuteProcessor, Matcher # type: ignore
from overrides import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, cast
import json
from ecs_systems.components import AppearanceComponent, BodyComponent, ActorComponent, CurrentUsingPropComponent
import ecs_systems.cn_builtin_prompt as builtin_prompt
from file_system.files_def import PropFile
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask

# todo
class UpdateAppearanceSystem(InitializeProcessor, ExecuteProcessor):

    """
    更新外观信息的系统
    """

    def __init__(self, context: RPGEntitasContext, system_name: str) -> None:
        self._context: RPGEntitasContext = context
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
        world_entity = self._context.get_world_entity(self._system_name)
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
                entity.replace(AppearanceComponent, name, body, hash_code)
###############################################################################################################################################
    # 有衣服的，请求更新，通过LLM来推理外观。
    def request_update_appearance(self, actors_body_and_clothe:  Dict[str, tuple[str, str]], world_entity: Entity) -> bool:
        assert world_entity is not None
        final_prompt = builtin_prompt.actors_body_and_clothe_prompt(actors_body_and_clothe)
        if final_prompt == "":
            return False

        # 请求更新
        safe_name = self._context.safe_get_entity_name(world_entity)
        try:

            agent = self._context._langserve_agent_system.get_agent(safe_name)
            assert agent is not None
            task = LangServeAgentRequestTask.create_without_any_context(agent, final_prompt)
            assert task is not None

            if task is None:
                logger.error(f"{safe_name} request error.")
                return False

            #
            response = task.request()
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
            entity.replace(AppearanceComponent, name, appearance, hash_code)
###############################################################################################################################################
    # 获取所有的角色的身体和衣服
    def get_actors_body_and_clothe(self) -> Dict[str, tuple[str, str]]:
        ret: Dict[str, tuple[str, str]] = {}
        
        actor_entities = self._context.get_group(Matcher(all_of = [AppearanceComponent, BodyComponent, ActorComponent])).entities
        for actor_entity in actor_entities:
            
            appearance_comp = actor_entity.get(AppearanceComponent)
            if appearance_comp.appearance != "":
                continue

            name = cast(ActorComponent, actor_entity.get(ActorComponent)).name
            body = self.get_body(actor_entity)
            clothe = self.get_current_clothe(actor_entity)
            ret[name] = (body, clothe)

        return ret
###############################################################################################################################################
    # 获取衣服的描述 todo。现在就返回了第一个衣服的描述
    def get_current_clothe(self, entity: Entity) -> str:
        if not entity.has(CurrentUsingPropComponent):
            return ""
    
        current_using_prop_comp = entity.get(CurrentUsingPropComponent)
        current_clothe_prop_file = self._context._file_system.get_file(PropFile, current_using_prop_comp.name, current_using_prop_comp.clothes)
        if current_clothe_prop_file is None:
            return ""

        return current_clothe_prop_file.appearance
###############################################################################################################################################
    # 获取身体的描述。
    def get_body(self, entity: Entity) -> str:
        if not entity.has(BodyComponent):
            return ""
        body_comp = entity.get(BodyComponent)
        return cast(str, body_comp.body)
###############################################################################################################################################
   
