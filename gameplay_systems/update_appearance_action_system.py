from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from overrides import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, Set, List, final
import json
from my_components.components import (
    AppearanceComponent,
    BodyComponent,
    ActorComponent,
    RPGCurrentClothesComponent,
)
from extended_systems.prop_file import PropFile
from my_agent.agent_task import AgentTask
from my_components.action_components import UpdateAppearanceAction
from rpg_game.rpg_game import RPGGame
from my_models.event_models import UpdateAppearanceEvent


################################################################################################################################################
def _generate_appearance_update_prompt(actor_name: str, appearance: str) -> str:
    return f"""# {actor_name} 的外观信息已更新
## 角色外观信息
{appearance}"""


################################################################################################################################################
def _generate_default_appearance_prompt(body: str, clothe: str) -> str:
    return body + f"""\n衣着:{clothe}""" if clothe != "" else " "


################################################################################################################################################
def _generate_reasoning_appearance_prompt(
    actors_body_and_clothe: Dict[str, tuple[str, str]]
) -> str:
    appearance_info_list: List[str] = []
    actor_name_list: List[str] = []
    for name, (body, clothe) in actors_body_and_clothe.items():
        appearance_info_list.append(
            f"""### {name}
- 裸身:{body}
- 衣服:{clothe}
"""
        )
        actor_name_list.append(name)

    dumps = json.dumps({name: "?" for name in actor_name_list}, ensure_ascii=False)

    # 最后的合并
    ret_prompt = f"""# 请根据 裸身 与 衣服，生成当前的角色外观的描述。
## 提供给你的信息
{"\n".join(appearance_info_list)}

## 推理逻辑
- 第1步:如角色有衣服。则代表“角色穿着衣服”。最终推理结果为:裸身的信息结合衣服信息。并且是以第三者视角能看到的样子去描述。
    - 注意！部分身体部位会因穿着衣服被遮蔽。请根据衣服的信息进行推理。
    - 衣服的样式，袖子与裤子等信息都会影响最终外观。
    - 面具（遮住脸），帽子（遮住头部，或部分遮住脸）等头部装饰物也会影响最终外观。
    - 被遮住的部位（因为站在第三者视角就无法看见），不需要再次提及，不要出现在推理结果中，如果有，需要删除。
    - 注意！错误的句子：胸前的黑色印记被衣服遮盖住，无法看见。
- 第2步:如角色无衣服，推理结果为角色当前为裸身。
    - 注意！如果是人形角色，裸身意味着穿着内衣!
    - 如果是动物，怪物等非人角色，就是最终外观信息。
- 第3步:将推理结果进行适度润色。

## 输出格式指南

### 输出格式（请根据下面的示意, 确保你的输出严格遵守相应的结构)
{dumps}

### 注意事项
- '?'就是你推理出来的结果(结果中可以不用再提及角色名字)，你需要将其替换为你的推理结果。
- 所有文本输出必须为第3人称。
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。
"""
    return ret_prompt


####################################################################################################
@final
class UpdateAppearanceActionSystem(ReactiveProcessor):

    def __init__(
        self, context: RPGEntitasContext, rpg_game: RPGGame, system_name: str
    ) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
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
        self.remove_all(entities)

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

        #
        self.add_update_appearance_human_message(actor_entities)

    ###############################################################################################################################################
    def default_update(self, input_data: Dict[str, tuple[str, str]]) -> None:

        context = self._context
        for name, (body, clothe) in input_data.items():

            if body == "":
                # assert False, f"body is empty, name: {name}"
                logger.error(f"body is empty, name: {name}")
                continue

            default_appearance = _generate_default_appearance_prompt(body, clothe)

            entity = context.get_actor_entity(name)
            assert entity is not None, f"entity is None, name: {name}"

            entity.replace(AppearanceComponent, name, default_appearance)

    ###############################################################################################################################################
    def request(self, input_data: Dict[str, tuple[str, str]], agent_name: str) -> bool:

        if len(input_data) == 0:
            return False

        agent = self._context._langserve_agent_system.get_agent(agent_name)
        if agent is None:
            return False

        prompt = _generate_reasoning_appearance_prompt(input_data)

        task = AgentTask.create_standalone(agent, prompt)
        if task.request() is None:
            logger.error(f"{agent_name} request response is None.")
            return False

        try:

            json_obj: Dict[str, str] = json.loads(task.response_content)
            self.on_success(json_obj)

        except Exception as e:
            logger.error(f"json.loads error: {e}")
            return False

        return True

    ###############################################################################################################################################
    def on_success(self, _json_: Dict[str, str]) -> None:
        context = self._context
        for name, appearance in _json_.items():
            entity = context.get_actor_entity(name)
            if entity is None:
                continue
            # hash_code = hash(appearance)
            entity.replace(AppearanceComponent, name, appearance)

    ###############################################################################################################################################
    def make_data(self, actor_entities: Set[Entity]) -> Dict[str, tuple[str, str]]:

        ret: Dict[str, tuple[str, str]] = {}

        for actor_entity in actor_entities:
            name = actor_entity.get(ActorComponent).name
            body = self.get_body(actor_entity)
            clothe = self.get_current_clothe(actor_entity)
            ret[name] = (body, clothe)

        return ret

    ###############################################################################################################################################
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
    def get_body(self, entity: Entity) -> str:
        if not entity.has(BodyComponent):
            return ""
        body_comp = entity.get(BodyComponent)
        return body_comp.body

    ###############################################################################################################################################
    def add_update_appearance_human_message(self, actor_entities: Set[Entity]) -> None:
        for actor_entity in actor_entities:
            current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
            if current_stage_entity is None:
                continue

            appearance_comp = actor_entity.get(AppearanceComponent)

            # 广播给场景内的所有人，包括自己。
            self._context.broadcast_event_in_stage(
                current_stage_entity,
                UpdateAppearanceEvent(
                    message_content=_generate_appearance_update_prompt(
                        appearance_comp.name, appearance_comp.appearance
                    )
                ),
            )

    ###############################################################################################################################################
    def remove_all(self, entities: List[Entity]) -> None:
        for entity in entities:
            if entity.has(UpdateAppearanceAction):
                entity.remove(UpdateAppearanceAction)

    ###############################################################################################################################################
