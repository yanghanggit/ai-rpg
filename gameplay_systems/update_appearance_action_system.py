from dataclasses import dataclass
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from overrides import override
from game.rpg_game_context import RPGGameContext
from loguru import logger
from typing import Dict, Final, List, final, Optional
import json
from components.components import (
    FinalAppearanceComponent,
    BaseFormComponent,
    ActorComponent,
    ClothesComponent,
    AgentPingFlagComponent,
    KickOffContentComponent,
    WeaponComponent,
)
from extended_systems.prop_file import PropFile
from agent.agent_request_handler import AgentRequestHandler
from components.actions import UpdateAppearanceAction
from game.rpg_game import RPGGame
from models.event_models import UpdateAppearanceEvent
from agent.lang_serve_agent import LangServeAgent
import gameplay_systems.task_request_utils


################################################################################################################################################
def _generate_appearance_update_prompt(actor_name: str, appearance: str) -> str:
    return f"""# 发生事件: {actor_name} 的外观信息更新
{appearance}"""


################################################################################################################################################
def _generate_default_appearance_prompt(
    actor_name: str, base_form: str, clothe: str, weapon: str
) -> str:
    assert base_form != "", "base_form is empty."
    if clothe == "":
        return base_form

    return f"""{actor_name}
基础形态: {base_form}
持有武器: {weapon if weapon != "" else "无"}
穿着衣服: {clothe if clothe != "" else "无"}"""


################################################################################################################################################
def _generate_appearance_reasoning_prompt(
    base_form_and_clothe_info: Dict[str, tuple[str, str, str]]
) -> str:

    reference_info: List[str] = []
    for name, (base_form, clothe, weapon) in base_form_and_clothe_info.items():
        reference_info.append(
            f"""### {_generate_default_appearance_prompt(name, base_form, clothe, weapon)}"""
        )

    appearance_json_structure = json.dumps(
        {name: "?" for name in base_form_and_clothe_info.keys()}, ensure_ascii=False
    )

    return f"""# 请根据基础形态和衣着的信息生成角色的外观描述。

## 提供信息
{"\n".join(reference_info)}

## 推理逻辑
1. 角色穿衣：如角色有衣服，结合基础形态和衣服信息生成外观描述。注意：
    - 部分身体部位（基础形态）会因穿着衣服被遮蔽，应忽略被遮蔽的部位。
    - 衣服的样式和细节（如袖子、裤子、面具、帽子）会影响外观。
    - 避免描述被遮蔽的部位，例如“胸前的印记被衣服遮盖住”。
2. 角色无衣：如角色无衣服，人形角色为穿内衣状态，非人角色直接描述基础形态外观。
3. 角色持有武器：如角色有武器，则最终结果应融入武器的外观描述。没有则不需要描述。
4. 输出内容要求简短。

## 输出要求 
### 输出格式指南
请严格遵循以下JSON结构示例: {appearance_json_structure}
### 注意事项
- 输出一个完整JSON对象。包含上述键中的一个或多个，不得重复或使用未定义的键。
- 将“?”替换为推理结果，无需重复角色全名。
- 输出必须为第3人称。
- 输出中不应包含多余文本或解释。
- 不要使用```json```来封装内容。"""


####################################################################################################
####################################################################################################
####################################################################################################


@dataclass
class InternalProcessData:
    actor_name: str
    actor_entity: Entity
    base_form: str
    weapon: str
    clothe: str


###############################################################################################################################################
@final
class UpdateAppearanceActionSystem(ReactiveProcessor):

    def __init__(
        self, context: RPGGameContext, rpg_game: RPGGame, world_system_name: str
    ) -> None:
        super().__init__(context)
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game
        self._world_system_name: str = str(world_system_name)
        self._batch_size: Final[int] = 5
        self._react_entities_copy: List[Entity] = []

    ###############################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(UpdateAppearanceAction): GroupEvent.ADDED}

    ###############################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(UpdateAppearanceAction)
            and entity.has(ActorComponent)
            and entity.has(BaseFormComponent)
        )

    ###############################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        self._react_entities_copy = entities.copy()

    ###############################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        if len(self._react_entities_copy) == 0:
            return
        await self._process_appearance_update(self._react_entities_copy)
        self._react_entities_copy.clear()

    ###############################################################################################################################################
    async def _process_appearance_update(self, entities: List[Entity]) -> None:

        actor_appearance_info = self._generate_actor_appearance_info((entities))
        if len(actor_appearance_info) == 0:
            return

        # 没有衣服的，直接更新外观，也是默认设置，防止世界系统无法推理
        self._apply_default(actor_appearance_info)

        # 有衣服的，请求更新，通过LLM来推理外观
        await self._process_world_system_update_appearance(
            actor_appearance_info, self._batch_size
        )

        # 广播更新外观事件
        self._notify_appearance_change_event((entities))

        # 最后必须清除UpdateAppearanceAction
        self._clear_appearance_actions(entities)

    ###############################################################################################################################################
    async def _process_world_system_update_appearance(
        self, actor_appearance_info: List[InternalProcessData], batch_size: int
    ) -> None:

        assert batch_size > 0, "batch_size must be greater than 0."
        if (
            len(actor_appearance_info) == 0
            or self.world_system_entity is None
            or not self.world_system_entity.has(AgentPingFlagComponent)
            or not self.world_system_entity.has(KickOffContentComponent)
            or batch_size <= 0
        ):
            return

        # 如果 actor_appearance_info过长，需要分批推理，每次推理最多5个
        batch_processing_tasks: List[AgentRequestHandler] = []
        for i in range(0, len(actor_appearance_info), batch_size):
            batch = actor_appearance_info[i : i + batch_size]
            batch_processing_tasks.append(
                self._generate_agent_appearance_task(
                    batch, self._context.safe_get_agent(self.world_system_entity)
                )
            )

        # 并发
        await gameplay_systems.task_request_utils.gather(
            [task for task in batch_processing_tasks]
        )

        # 处理
        for process_task in batch_processing_tasks:
            self._process_agent_appearance_task(process_task)

    ###############################################################################################################################################
    @property
    def world_system_entity(self) -> Optional[Entity]:
        return self._context.get_world_entity(self._world_system_name)

    ###############################################################################################################################################
    def _apply_default(self, appearance_info: List[InternalProcessData]) -> None:

        for data in appearance_info:
            assert data.base_form != "", "base_form is empty."
            if data.base_form == "":
                continue

            data.actor_entity.replace(
                FinalAppearanceComponent,
                data.actor_name,
                _generate_default_appearance_prompt(
                    data.actor_name,
                    data.base_form,
                    data.clothe,
                    data.weapon,
                ),
            )

    ###############################################################################################################################################
    def _generate_agent_appearance_task(
        self,
        batch_appearance_info: List[InternalProcessData],
        world_system_agent: LangServeAgent,
    ) -> AgentRequestHandler:

        gen_mapping = {
            data.actor_name: (
                data.base_form,
                data.clothe,
                data.weapon,
            )
            for data in batch_appearance_info
        }

        return AgentRequestHandler.create_without_context(
            world_system_agent,
            _generate_appearance_reasoning_prompt(gen_mapping),
        )

    ###############################################################################################################################################
    def _process_agent_appearance_task(
        self,
        agent_task: AgentRequestHandler,
    ) -> None:

        try:

            json_reponse: Dict[str, str] = json.loads(agent_task.response_content)
            self._update_appearance_components(json_reponse)

        except Exception as e:
            logger.error(f"json.loads error: {e}")

    ###############################################################################################################################################
    def _update_appearance_components(
        self, appearance_change_map: Dict[str, str]
    ) -> None:
        for name, appearance in appearance_change_map.items():
            entity = self._context.get_actor_entity(name)
            assert entity is not None, f"entity is None, name: {name}"
            if entity is None:
                continue
            entity.replace(FinalAppearanceComponent, name, appearance)

    ###############################################################################################################################################
    def _generate_actor_appearance_info(
        self, actor_entities: List[Entity]
    ) -> List[InternalProcessData]:

        ret: List[InternalProcessData] = []
        for actor_entity in actor_entities:
            ret.append(
                InternalProcessData(
                    actor_name=actor_entity.get(ActorComponent).name,
                    actor_entity=actor_entity,
                    base_form=actor_entity.get(BaseFormComponent).base_form,
                    weapon=self._extract_weapon_appearance(actor_entity),
                    clothe=self._extract_clothing_appearance(actor_entity),
                )
            )

        return ret

    ###############################################################################################################################################
    def _extract_clothing_appearance(self, actor_entity: Entity) -> str:
        if not actor_entity.has(ClothesComponent):
            return ""

        clothes_comp = actor_entity.get(ClothesComponent)
        clothe_prop_file = self._context.file_system.get_file(
            PropFile, clothes_comp.name, clothes_comp.prop_name
        )
        assert (
            clothe_prop_file is not None
        ), f"clothe_prop_file is None, name: {clothes_comp.name}"
        if clothe_prop_file is None:
            return ""

        return f"""{clothe_prop_file.name}。 {clothe_prop_file.appearance}"""

    ###############################################################################################################################################
    def _extract_weapon_appearance(self, actor_entity: Entity) -> str:
        if not actor_entity.has(WeaponComponent):
            return ""

        weapon_comp = actor_entity.get(WeaponComponent)
        weapon_prop_file = self._context.file_system.get_file(
            PropFile, weapon_comp.name, weapon_comp.prop_name
        )
        assert (
            weapon_prop_file is not None
        ), f"weapon_prop_file is None, name: {weapon_comp.name}"
        if weapon_prop_file is None:
            return ""

        return f"""{weapon_prop_file.name}。 {weapon_prop_file.appearance}"""

    ###############################################################################################################################################
    def _notify_appearance_change_event(self, actor_entities: List[Entity]) -> None:
        for actor_entity in actor_entities:
            current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
            if current_stage_entity is None:
                continue

            appearance_comp = actor_entity.get(FinalAppearanceComponent)
            self._context.broadcast_event(
                current_stage_entity,
                UpdateAppearanceEvent(
                    message=_generate_appearance_update_prompt(
                        appearance_comp.name, appearance_comp.final_appearance
                    )
                ),
            )

    ###############################################################################################################################################
    def _clear_appearance_actions(self, entities: List[Entity]) -> None:
        for entity in entities:
            if entity.has(UpdateAppearanceAction):
                entity.remove(UpdateAppearanceAction)

    ###############################################################################################################################################
