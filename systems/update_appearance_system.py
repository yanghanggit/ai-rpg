from overrides import override
from entitas import Entity, InitializeProcessor, ExecuteProcessor, Matcher # type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from typing import Dict, List, cast, Set
from auxiliary.lang_serve_agent_system import LangServeAgentSystem, AgentRequestOption
import json
from auxiliary.components import AppearanceComponent, BodyComponent, ActorComponent

###############################################################################################################################################
class UpdateAppearanceSystem(InitializeProcessor, ExecuteProcessor):
    def __init__(self, context: ExtendedContext, system_name: str) -> None:
        self.context: ExtendedContext = context
        self.system_name: str = str(system_name)
        assert len(self.system_name) > 0
###############################################################################################################################################
    @override
    def initialize(self) -> None:
        pass
###############################################################################################################################################
    @override
    def execute(self) -> None:

        context = self.context
        world_entity = context.get_world_entity(self.system_name)
        if world_entity is None:
            logger.warning(f"{self.system_name}, world_entity is None.")
            return
        
        actors_body_and_clothe = self.get_actors_body_and_clothe()
        if len(actors_body_and_clothe) == 0:
            return
        
        # 没有衣服的，直接更新外形
        self.update_appearance_without_clothe(actors_body_and_clothe)
        # 有衣服的，请求更新，通过LLM来推理外观
        self.update_appearance_request(actors_body_and_clothe)
###############################################################################################################################################
    def update_appearance_without_clothe(self, actors_body_and_clothe:  Dict[str, tuple[str, str]]) -> None:
        context = self.context
        for name, (body, clothe) in actors_body_and_clothe.items():
            if clothe == "" and body != "":
                entity = context.get_actor_entity(name)
                assert entity is not None
                self.update_appearance_by_body(entity, name)
###############################################################################################################################################
    def update_appearance_request(self, actors_body_and_clothe:  Dict[str, tuple[str, str]]) -> None:
        prompt_list_of_actor: List[str] = []
        actor_names: List[str] = []
        for name, (body, clothe) in actors_body_and_clothe.items():

            if clothe == "":
                logger.info(f"clothe is empty, name: {name}") # 不穿衣服的不更新
                continue

            prompt_of_actor = f"""### {name}
- 角色外形:{body}
- 衣服:{clothe}
"""
            prompt_list_of_actor.append(prompt_of_actor)
            actor_names.append(name)

        #
        batch_str = "\n".join(prompt_list_of_actor)
        assert len(batch_str) > 0

        #
        appearance_json = {name: "?" for name in actor_names}
        appearance_json_str = json.dumps(appearance_json, ensure_ascii = False)

        final_prompt = f"""# 请更新角色外形：根据‘角色外形’与‘衣服’，生成最终的角色外形的描述。
## 角色列表
{batch_str}
## 输出格式指南
### 请根据下面的示意, 确保你的输出严格遵守相应的结构。
{appearance_json_str}
### 注意事项
- '?'就是你推理出来的结果(注意结果中可以不用再提及角色的名字)，你需要将其替换为你的推理结果。
- 所有文本输出必须为第3人称。
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。
"""
        logger.debug(f"final_prompt: {final_prompt}")

        # 请求更新
        agent_connect_system: LangServeAgentSystem = self.context.agent_connect_system
        try:
            response = agent_connect_system.agent_request(self.system_name, final_prompt, AgentRequestOption.DO_NOT_ADD_MESSAGE_TO_CHAT_HISTORY)
            if response is None:
                return
            logger.info(f"{self.system_name} request done.")
            json_response: Dict[str, str] = json.loads(response)
            self.update_after_requst(json_response)
        except Exception as e:
            logger.error(f"{self.system_name} request error = {e}")
###############################################################################################################################################
    def update_after_requst(self, json_response: Dict[str, str]) -> None:
        context = self.context
        for name, appearance in json_response.items():
            entity = context.get_actor_entity(name)
            if entity is None:
                logger.error(f"update_after_requst, entity is None, name: {name}")
                continue
            entity.replace(AppearanceComponent, appearance)
            logger.debug(f"{name}, update_after_requst: {appearance}")
###############################################################################################################################################
    def get_actors_body_and_clothe(self) -> Dict[str, tuple[str, str]]:
        res: Dict[str, tuple[str, str]] = {}
        actors: Set[Entity] = self.context.get_group(Matcher(all_of = [AppearanceComponent, BodyComponent, ActorComponent])).entities
        for _actor in actors:
            name = cast(ActorComponent, _actor.get(ActorComponent)).name
            body = self.get_body(_actor)
            clothe = self.get_clothe(_actor)
            logger.debug(f"actor: {name}, body: {body}, clothe: {clothe}")
            res[name] = (body, clothe)
        return res
###############################################################################################################################################
    def get_clothe(self, entity: Entity) -> str:
        filesystem = self.context.file_system
        safename = self.context.safe_get_entity_name(entity)            
        files = filesystem.get_prop_files(safename)
        for _file in files:
            if _file._prop.is_clothes():
                return _file._prop._description
        return "" 
###############################################################################################################################################
    def get_body(self, entity: Entity) -> str:
        if not entity.has(BodyComponent):
            return ""
        body_comp: BodyComponent = entity.get(BodyComponent)
        return cast(str, body_comp.body)
###############################################################################################################################################
    def update_appearance_by_body(self, entity: Entity, debug_name: str) -> None:
        assert entity.has(AppearanceComponent)
        assert entity.has(BodyComponent)
        body = self.get_body(entity)
        assert body != ""
        entity.replace(AppearanceComponent, body)
        logger.debug(f"{debug_name}, update_appearance_by_body: {body}")
###############################################################################################################################################
   
