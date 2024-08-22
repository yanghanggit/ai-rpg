from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from overrides import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, cast, Set
import json
from ecs_systems.components import (
    AppearanceComponent,
    BodyComponent,
    ActorComponent,
    RPGCurrentClothesComponent,
)
import ecs_systems.cn_builtin_prompt as builtin_prompt
from file_system.files_def import PropFile
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask
from ecs_systems.action_components import UpdateAppearanceAction


class UpdateAppearanceActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, system_name: str) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._system_name: str = str(system_name)

    ####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(UpdateAppearanceAction): GroupEvent.ADDED}

    ####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(UpdateAppearanceAction)
            and entity.has(ActorComponent)
            and entity.has(BodyComponent)
        )

    ####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        world_entity = self._context.get_world_entity(self._system_name)
        assert world_entity is not None
        self.handle_all(world_entity, set(entities))

    ###############################################################################################################################################
    def handle_all(self, world_entity: Entity, actor_entities: Set[Entity]) -> None:

        if len(actor_entities) == 0 or world_entity is None:
            return

        input_data = self.make_data(actor_entities)
        if len(input_data) == 0:
            return

        # 没有衣服的，直接更新外观
        self.default_update(input_data)

        # 有衣服的，请求更新，通过LLM来推理外观
        world_system_agent_name = self._context.safe_get_entity_name(world_entity)
        self.request(input_data, world_system_agent_name)

    ###############################################################################################################################################
    # 没有衣服的，就直接更新外观，一般是动物类的，或者非人类的。
    def default_update(self, input_data: Dict[str, tuple[str, str]]) -> None:

        context = self._context
        for name, (body, clothe) in input_data.items():

            if body == "":
                assert False, f"body is empty, name: {name}"
                continue

            default_appearance = body + clothe if clothe != "" else " "

            entity = context.get_actor_entity(name)
            assert entity is not None, f"entity is None, name: {name}"

            entity.replace(
                AppearanceComponent, name, default_appearance, hash(default_appearance)
            )

    ###############################################################################################################################################
    # 有衣服的，请求更新，通过LLM来推理外观。
    def request(self, input_data: Dict[str, tuple[str, str]], agent_name: str) -> bool:

        if len(input_data) == 0:
            return False

        agent = self._context._langserve_agent_system.get_agent(agent_name)
        if agent is None:
            return False

        prompt = builtin_prompt.make_gen_appearance_prompt(input_data)

        task = LangServeAgentRequestTask.create_without_any_context(agent, prompt)
        if task is None:
            return False

        response = task.request()
        if response is None:
            logger.error(f"{agent_name} request response is None.")
            return False

        _json_: Dict[str, str] = json.loads(response)
        self.on_success(_json_)
        return True

    ###############################################################################################################################################
    # 请求成功后的处理，就是把AppearanceComponent 设置一遍
    def on_success(self, _json_: Dict[str, str]) -> None:
        context = self._context
        for name, appearance in _json_.items():
            entity = context.get_actor_entity(name)
            if entity is None:
                continue
            hash_code = hash(appearance)
            entity.replace(AppearanceComponent, name, appearance, hash_code)

    ###############################################################################################################################################
    # 获取所有的角色的身体和衣服
    def make_data(self, actor_entities: Set[Entity]) -> Dict[str, tuple[str, str]]:

        ret: Dict[str, tuple[str, str]] = {}

        for actor_entity in actor_entities:
            name = actor_entity.get(ActorComponent).name
            body = self.get_body(actor_entity)
            clothe = self.get_current_clothe(actor_entity)
            ret[name] = (body, clothe)

        return ret

    ###############################################################################################################################################
    # 获取衣服的描述 todo。现在就返回了第一个衣服的描述
    def get_current_clothe(self, entity: Entity) -> str:
        if not entity.has(RPGCurrentClothesComponent):
            return ""

        current_clothes_comp = entity.get(RPGCurrentClothesComponent)
        current_clothe_prop_file = self._context._file_system.get_file(
            PropFile, current_clothes_comp.name, current_clothes_comp.propname
        )
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
