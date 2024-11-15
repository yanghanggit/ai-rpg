from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from overrides import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, Set, List, final, Optional
import json
from my_components.components import (
    AppearanceComponent,
    BodyComponent,
    ActorComponent,
    ClothesComponent,
)
from extended_systems.prop_file import PropFile
from my_agent.agent_task import AgentTask
from my_components.action_components import UpdateAppearanceAction
from rpg_game.rpg_game import RPGGame
from my_models.event_models import UpdateAppearanceEvent


################################################################################################################################################
def _generate_appearance_update_prompt(actor_name: str, appearance: str) -> str:
    return f"""# 发生事件: {actor_name} 的外观信息更新
{appearance}"""


################################################################################################################################################
def _generate_default_appearance_prompt(body: str, clothe: str) -> str:
    assert body != "", "body is empty."
    if clothe == "":
        return body

    return body + f"""\n衣着:{clothe}"""


################################################################################################################################################
def _generate_appearance_reasoning_prompt(
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
        self, context: RPGEntitasContext, rpg_game: RPGGame, world_system_name: str
    ) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._world_system_name: str = str(world_system_name)

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
        self._update_entity_appearance(
            self._context.get_world_entity(self._world_system_name), set(entities)
        )
        self._clear_appearance_actions(entities)

    ###############################################################################################################################################
    def _update_entity_appearance(
        self, world_system_entity: Optional[Entity], actor_entities: Set[Entity]
    ) -> None:

        if len(actor_entities) == 0:
            return

        actor_appearance_data = self._generate_actor_appearance_data(actor_entities)
        if len(actor_appearance_data) == 0:
            return

        # 没有衣服的，直接更新外观
        self._apply_default_appearance(actor_appearance_data)

        # 有衣服的，请求更新，通过LLM来推理外观
        self._process_appearance_update_request(
            actor_appearance_data, world_system_entity
        )

        # 广播更新外观事件
        self._broadcast_appearance_update_event(actor_entities)

    ###############################################################################################################################################
    def _apply_default_appearance(self, input_data: Dict[str, tuple[str, str]]) -> None:

        context = self._context
        for name, (body, clothe) in input_data.items():

            if body == "":
                logger.error(f"body is empty, name: {name}")
                continue

            default_appearance = _generate_default_appearance_prompt(body, clothe)

            entity = context.get_actor_entity(name)
            assert entity is not None, f"entity is None, name: {name}"

            entity.replace(AppearanceComponent, name, default_appearance)

    ###############################################################################################################################################
    def _process_appearance_update_request(
        self,
        actor_appearance_data: Dict[str, tuple[str, str]],
        world_system_entity: Optional[Entity],
    ) -> bool:

        if len(actor_appearance_data) == 0 or world_system_entity is None:
            return False

        safe_name = self._context.safe_get_entity_name(world_system_entity)
        agent = self._context.agent_system.get_agent(safe_name)
        if agent is None:
            return False

        prompt = _generate_appearance_reasoning_prompt(actor_appearance_data)

        appearance_update_task = AgentTask.create_without_context(agent, prompt)
        if appearance_update_task.request() is None:
            logger.error(f"{safe_name} request response is None.")
            return False

        try:

            appearance_json_response: Dict[str, str] = json.loads(
                appearance_update_task.response_content
            )
            self._update_appearance_entities(appearance_json_response)

        except Exception as e:
            logger.error(f"json.loads error: {e}")
            return False

        return True

    ###############################################################################################################################################
    def _update_appearance_entities(self, _json_: Dict[str, str]) -> None:
        context = self._context
        for name, appearance in _json_.items():
            entity = context.get_actor_entity(name)
            if entity is None:
                continue
            entity.replace(AppearanceComponent, name, appearance)

    ###############################################################################################################################################
    def _generate_actor_appearance_data(
        self, actor_entities: Set[Entity]
    ) -> Dict[str, tuple[str, str]]:

        ret: Dict[str, tuple[str, str]] = {}
        for actor_entity in actor_entities:
            ret[actor_entity.get(ActorComponent).name] = (
                actor_entity.get(BodyComponent).body,
                self._retrieve_current_clothing(actor_entity),
            )

        return ret

    ###############################################################################################################################################
    def _retrieve_current_clothing(self, entity: Entity) -> str:
        if not entity.has(ClothesComponent):
            return ""

        current_clothes_comp = entity.get(ClothesComponent)
        current_clothe_prop_file = self._context._file_system.get_file(
            PropFile, current_clothes_comp.name, current_clothes_comp.propname
        )
        if current_clothe_prop_file is None:
            return ""

        return current_clothe_prop_file.appearance

    ###############################################################################################################################################
    def _broadcast_appearance_update_event(self, actor_entities: Set[Entity]) -> None:
        for actor_entity in actor_entities:
            current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
            if current_stage_entity is None:
                continue

            appearance_comp = actor_entity.get(AppearanceComponent)
            self._context.broadcast_event_in_stage(
                current_stage_entity,
                UpdateAppearanceEvent(
                    message=_generate_appearance_update_prompt(
                        appearance_comp.name, appearance_comp.appearance
                    )
                ),
            )

    ###############################################################################################################################################
    def _clear_appearance_actions(self, entities: List[Entity]) -> None:
        for entity in entities:
            if entity.has(UpdateAppearanceAction):
                entity.remove(UpdateAppearanceAction)

    ###############################################################################################################################################
