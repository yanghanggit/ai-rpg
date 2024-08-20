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
    CurrentUsingPropComponent,
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
        return entity.has(UpdateAppearanceAction)

    ####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:

        world_entity = self._context.get_world_entity(self._system_name)
        if world_entity is None:
            # 没有这个对象，就认为这个系统不成立。
            logger.warning(f"{self._system_name}, world_entity is None.")
            return

        names: Set[str] = set()
        for entity in entities:
            safe_name = self._context.safe_get_entity_name(entity)
            names.add(safe_name)

        self.handle(world_entity, names)

    ###############################################################################################################################################
    def handle(self, world_entity: Entity, need_update_actors: Set[str]) -> None:
        assert world_entity is not None
        actors_body_and_clothe = self.get_actors_body_and_clothe(need_update_actors)
        if len(actors_body_and_clothe) == 0:
            return
        # 没有衣服的，直接更新外观
        self.imme_update_appearance(actors_body_and_clothe)
        # 有衣服的，请求更新，通过LLM来推理外观
        self.request_update_appearance(actors_body_and_clothe, world_entity)

    ###############################################################################################################################################
    # 没有衣服的，就直接更新外观，一般是动物类的，或者非人类的。
    def imme_update_appearance(
        self, actors_body_and_clothe: Dict[str, tuple[str, str]]
    ) -> None:

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
    def request_update_appearance(
        self, actors_body_and_clothe: Dict[str, tuple[str, str]], world_entity: Entity
    ) -> bool:
        # 请求更新
        safe_name = self._context.safe_get_entity_name(world_entity)

        agent = self._context._langserve_agent_system.get_agent(safe_name)
        if agent is None:
            return False

        final_prompt = builtin_prompt.actors_body_and_clothe_prompt(
            actors_body_and_clothe
        )
        if final_prompt == "":
            return False

        task = LangServeAgentRequestTask.create_without_any_context(agent, final_prompt)
        if task is None:
            return False

        response = task.request()
        if response is None:
            logger.error(f"{safe_name} request response is None.")
            return False

        json_response: Dict[str, str] = json.loads(response)
        self.on_request_success(json_response)
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
    def get_actors_body_and_clothe(
        self, need_update_actors: Set[str]
    ) -> Dict[str, tuple[str, str]]:
        ret: Dict[str, tuple[str, str]] = {}

        actor_entities = self._context.get_group(
            Matcher(all_of=[AppearanceComponent, BodyComponent, ActorComponent])
        ).entities

        for actor_entity in actor_entities:

            appearance_comp = actor_entity.get(AppearanceComponent)

            if appearance_comp.name not in need_update_actors:
                continue

            name = actor_entity.get(ActorComponent).name
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
        current_clothe_prop_file = self._context._file_system.get_file(
            PropFile, current_using_prop_comp.name, current_using_prop_comp.clothes
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
