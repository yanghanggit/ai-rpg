from dataclasses import dataclass
from entitas import Matcher, ExecuteProcessor, Entity  # type: ignore
from my_components.action_components import (
    TagAction,
    AnnounceAction,
    InspectAction,
)
from my_components.components import (
    BaseFormComponent,
    SkillComponent,
    DestroyComponent,
    DirectSkillComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, List, Set, Optional
from loguru import logger
from extended_systems.prop_file import (
    PropFile,
    generate_skill_prop_file_prompt,
    generate_skill_accessory_prop_file_prompt,
)
import gameplay_systems.prompt_utils as prompt_utils
from my_agent.agent_task import AgentTask
from my_agent.agent_plan import AgentPlanResponse
from rpg_game.rpg_game import RPGGame
import gameplay_systems.file_system_utils
from my_models.event_models import AgentEvent
import gameplay_systems.skill_entity_utils
from my_agent.lang_serve_agent import LangServeAgent
from my_models.entity_models import Attributes
import gameplay_systems.prompt_utils


################################################################################################################################################
def _generate_error_summary_prompt(
    actor_name: str,
    inspector_tag: str,
    skill_command: str,
    inspector_content: str,
) -> str:

    return f"""# 提示: 系统推理与判断之后，判断结果为 {inspector_tag}
## 行动(技能)发起者
{actor_name}
## 技能指令内容
{skill_command}
## 系统判断的原因
{inspector_content}"""


################################################################################################################################################
def _generate_success_response_prompt(
    actor_name: str,
    inspector_tag: str,
    skill_command: str,
    inspector_content: str,
) -> str:

    return f"""# 提示: 系统推理与判断之后，判断结果为 {inspector_tag}。即系统经过判断后允许继续
## 行动(技能)发起者
{actor_name}
## 技能指令内容
{skill_command}
## 系统推理并润色后的结果
{inspector_content}"""


################################################################################################################################################
def _generate_world_harmony_inspector_prompt(
    actor_name: str,
    actor_base_form: str,
    skill_prop_files: List[PropFile],
    skill_accessory_prop_files: List[PropFile],
    skill_command: str,
) -> str:

    # 组织技能的提示词
    skill_prop_files_prompt: List[str] = []
    if len(skill_prop_files) > 0:
        for skill_file in skill_prop_files:
            assert skill_file.insight != "", "技能的洞察力不能为空"
            skill_prop_files_prompt.append(
                generate_skill_prop_file_prompt(skill_file, True)
            )
    if len(skill_prop_files_prompt) == 0:
        skill_prop_files_prompt.append("无任何技能")
        assert False, "技能不能为空"

    # 组织道具的提示词
    skill_accessory_prop_files_prompt: List[str] = []
    if len(skill_accessory_prop_files) > 0:
        for skill_accessory_prop_file in skill_accessory_prop_files:
            skill_accessory_prop_files_prompt.append(
                generate_skill_accessory_prop_file_prompt(skill_accessory_prop_file)
            )
    if len(skill_accessory_prop_files_prompt) == 0:
        skill_accessory_prop_files_prompt.append("未配置道具")

    return f"""# 提示: {actor_name} 准备使用技能。请你作为系统，判断其技能使用的合理性（是否符合游戏规则和世界观设计）。在尽量保证游戏乐趣的前提下，润色技能使用过程的描述。

## 技能规则摘要
{gameplay_systems.prompt_utils.skill_action_rule_prompt()}

## 输入信息
### {actor_name} 的基础形态
{actor_base_form}
### 技能信息
{"\n".join(skill_prop_files_prompt)}
### 配置道具信息
{"\n".join(skill_accessory_prop_files_prompt)}
### 技能指令内容
{skill_command}


## 判断的逻辑步骤
1. **道具优先**：
   - 如果存在“配置道具”，需要结合道具与技能的信息推理。
     - 如果推理结果违反游戏规则或世界观设计，则技能释放失败，标记为 {prompt_utils.SkillResultPromptTag.FAILURE}。
     - 如果推理结果合理，则技能释放成功，标记为 {prompt_utils.SkillResultPromptTag.SUCCESS}；如道具提供额外增益，则标记为 {prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}。
2. **无道具时**：
   - 判断角色基础形态是否满足技能释放条件。
     - 如果不符合，则技能释放失败，标记为 {prompt_utils.SkillResultPromptTag.FAILURE}。
     - 如果符合，则技能释放成功，标记为 {prompt_utils.SkillResultPromptTag.SUCCESS}；如角色信息有增益效果，则标记为 {prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}。

3. **正常释放**：
   - 如果技能无道具需求，且角色无特殊增益，技能按正常释放计算。
   
## 关于 {AnnounceAction.__name__} 的输出规则
1. 成功或大成功时：
   - 必须描述：技能使用者的全名，释放的技能名称和描述，技能目标的全名，配置的道具信息。
   - 描述需用逻辑合理且生动的句子，润色后以第三人称呈现。
   - 不需涉及目标被命中后的反应，仅限于技能释放的过程。
2. 失败时：
   - 必须描述：技能释放失败的原因。

## 关于 {InspectAction.__name__} 的输出规则
- 对结果的评估值规则：
  - {prompt_utils.SkillResultPromptTag.FAILURE}: 0。
  - {prompt_utils.SkillResultPromptTag.SUCCESS}: 100。
  - {prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}: 100~200。

## 输出要求
### 输出格式指南
请严格遵循以下 JSON 结构示例: 
{{
  "{AnnounceAction.__name__}": ["输出技能使用过程的描述（见上文）"],
  "{TagAction.__name__}": ["{prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS} 或 {prompt_utils.SkillResultPromptTag.SUCCESS} 或 {prompt_utils.SkillResultPromptTag.FAILURE}"],
  "{InspectAction.__name__}": ["一个0~200的数字，代表你对结果的评估值（见上文）"]
}}
### 例句
{{
  "AnnounceAction": ["某某角色施展了炫丽的火球术，目标锁定在前方的敌人，并使用了珍贵的魔法水晶作为催化剂。"],
  "TagAction": ["<大成功>"],
  "InspectAction": ["180"]
}}
### 注意事项
- 注意！不允许重复使用上述的键！ 
- 注意！不允许使用不在上述列表中的键！（即未定义的键位），注意看‘输出要求’
- 输出不得包含超出所需 JSON 格式的其他文本、解释或附加信息。
- 不要使用```json```来封装内容。"""


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
@final
class InternalPlanResponse(AgentPlanResponse):

    def __init__(self, name: str, response_content: str) -> None:
        super().__init__(name, response_content)

    @property
    def inspector_tag(self) -> str:

        action = self.get_action(TagAction.__name__)
        if action is None or len(action.values) == 0:
            return prompt_utils.SkillResultPromptTag.FAILURE

        if (
            action.values[0] == prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS
            or action.values[0] == prompt_utils.SkillResultPromptTag.SUCCESS
        ):
            return action.values[0]

        return prompt_utils.SkillResultPromptTag.FAILURE

    @property
    def inspector_content(self) -> str:
        return self._concatenate_values(AnnounceAction.__name__)

    @property
    def inspector_value(self) -> int:

        action = self.get_action(InspectAction.__name__)
        if action is None or len(action.values) == 0:
            return Attributes.BASE_VALUE_SCALE

        number_string = action.values[0]
        if not number_string.isdigit():
            return Attributes.BASE_VALUE_SCALE

        ret = int(number_string)
        ret = max(0, min(200, ret))
        return ret


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
@dataclass
class InternalProcessData:
    actor_entity: Entity
    skill_entity: Entity
    agent: LangServeAgent
    agent_task: AgentTask
    plan_response: InternalPlanResponse


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
@final
class SkillWorldHarmonyInspectorSystem(ExecuteProcessor):

    def __init__(
        self, context: RPGEntitasContext, rpg_game: RPGGame, world_system_name: str
    ) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._world_system_name: str = world_system_name

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ######################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        if self.world_system_entity is None or self.world_system_agent is None:
            logger.error("world_system_entity or world_system_agent is None")
            return

        # 只关注技能
        skill_entities = self._context.get_group(
            Matcher(
                all_of=[SkillComponent],
                none_of=[DestroyComponent, DirectSkillComponent],
            )
        ).entities.copy()

        # 组成成方便的数据结构
        internal_process_data = self._initialize_internal_process_data(
            skill_entities, self.world_system_agent
        )
        if len(internal_process_data) == 0:
            return

        await self._process_world_harmony_inspector(internal_process_data)

    ######################################################################################################################################################
    @property
    def world_system_entity(self) -> Optional[Entity]:
        return self._context.get_world_entity(self._world_system_name)

    ######################################################################################################################################################
    @property
    def world_system_agent(self) -> Optional[LangServeAgent]:
        if self.world_system_entity is None:
            return None

        return self._context.safe_get_agent(self.world_system_entity)

    ######################################################################################################################################################
    def _initialize_internal_process_data(
        self, internal_process_data: Set[Entity], world_system_agent: LangServeAgent
    ) -> List[InternalProcessData]:

        ret: List[InternalProcessData] = []
        for skill_entity in internal_process_data:
            skill_comp = skill_entity.get(SkillComponent)

            actor_entity = self._context.get_actor_entity(skill_comp.name)
            assert (
                actor_entity is not None
            ), f"actor_entity {skill_comp.name} not found."
            if actor_entity is None:
                continue

            ret.append(
                InternalProcessData(
                    actor_entity=actor_entity,
                    skill_entity=skill_entity,
                    agent=world_system_agent,
                    agent_task=AgentTask.create_without_context(world_system_agent, ""),
                    plan_response=InternalPlanResponse(skill_comp.name, ""),
                )
            )

        return ret

    ######################################################################################################################################################
    async def _process_world_harmony_inspector(
        self, internal_process_data: List[InternalProcessData]
    ) -> None:

        agent_tasks = self._generate_agent_tasks(internal_process_data)
        assert len(agent_tasks) > 0
        if len(agent_tasks) == 0:
            self._clear(internal_process_data)
            return

        responses = await AgentTask.gather(agent_tasks)
        if len(responses) == 0:
            logger.error("responses is empty")
            self._clear(internal_process_data)
            return

        self._assemble_process_responses(internal_process_data)
        self._handle_response_plans(internal_process_data)

    ######################################################################################################################################################
    def _handle_response_plans(
        self, internal_process_data: List[InternalProcessData]
    ) -> None:

        for process_data in internal_process_data:

            if (
                process_data.plan_response.inspector_tag
                == prompt_utils.SkillResultPromptTag.FAILURE
            ):
                self._notify_inspector_failure_event(process_data)
                gameplay_systems.skill_entity_utils.destroy_skill_entity(
                    process_data.skill_entity
                )
                continue

            assert (
                process_data.plan_response.inspector_tag
                == prompt_utils.SkillResultPromptTag.SUCCESS
                or process_data.plan_response.inspector_tag
                == prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS
            )
            self._notify_inspector_success_event(process_data)
            self._add_world_harmony_inspector_data(process_data)
            self._process_consumable_items(process_data)

    ######################################################################################################################################################
    def _process_consumable_items(self, process_data: InternalProcessData) -> None:

        data = gameplay_systems.skill_entity_utils.parse_skill_accessory_prop_files(
            context=self._context,
            skill_entity=process_data.skill_entity,
            actor_entity=process_data.actor_entity,
        )
        for prop_file_and_count in data:
            prop_file = prop_file_and_count[0]
            consume_count = prop_file_and_count[1]
            gameplay_systems.file_system_utils.consume_file(
                self._context.file_system, prop_file, consume_count
            )

    ######################################################################################################################################################
    def _add_world_harmony_inspector_data(
        self,
        process_data: InternalProcessData,
    ) -> None:

        assert process_data.plan_response is not None
        skill_comp = process_data.skill_entity.get(SkillComponent)
        process_data.skill_entity.replace(
            SkillComponent,
            skill_comp.name,
            skill_comp.command,
            skill_comp.skill_name,
            skill_comp.stage,
            skill_comp.targets,
            skill_comp.skill_accessory_props,
            process_data.plan_response.inspector_tag,
            process_data.plan_response.inspector_content,
            process_data.plan_response.inspector_value,
        )

    ######################################################################################################################################################
    def _assemble_process_responses(
        self, internal_process_data: List[InternalProcessData]
    ) -> None:

        for process_data in internal_process_data:
            process_data.plan_response = InternalPlanResponse(
                process_data.agent_task.agent_name,
                process_data.agent_task.response_content,
            )

    ######################################################################################################################################################
    def _clear(self, internal_process_data: List[InternalProcessData]) -> None:
        for process_data in internal_process_data:
            gameplay_systems.skill_entity_utils.destroy_skill_entity(
                process_data.skill_entity
            )

    ######################################################################################################################################################
    def _notify_inspector_success_event(
        self, process_data: InternalProcessData
    ) -> None:

        self._context.notify_event(
            set({process_data.actor_entity}),
            AgentEvent(
                message=_generate_success_response_prompt(
                    actor_name=self._context.safe_get_entity_name(
                        process_data.actor_entity
                    ),
                    inspector_tag=process_data.plan_response.inspector_tag,
                    skill_command=process_data.skill_entity.get(SkillComponent).command,
                    inspector_content=process_data.plan_response.inspector_content,
                )
            ),
        )

    ######################################################################################################################################################
    def _notify_inspector_failure_event(
        self, process_data: InternalProcessData
    ) -> None:

        self._context.notify_event(
            set({process_data.actor_entity}),
            AgentEvent(
                message=_generate_error_summary_prompt(
                    actor_name=self._context.safe_get_entity_name(
                        process_data.actor_entity
                    ),
                    inspector_tag=process_data.plan_response.inspector_tag,
                    skill_command=process_data.skill_entity.get(SkillComponent).command,
                    inspector_content=process_data.plan_response.inspector_content,
                )
            ),
        )

    ######################################################################################################################################################
    def _generate_agent_tasks(
        self,
        internal_process_data: List[InternalProcessData],
    ) -> List[AgentTask]:

        ret: List[AgentTask] = []
        for process_data in internal_process_data:

            prompt = _generate_world_harmony_inspector_prompt(
                self._context.safe_get_entity_name(process_data.actor_entity),
                process_data.actor_entity.get(BaseFormComponent).base_form,
                gameplay_systems.skill_entity_utils.parse_skill_prop_files(
                    context=self._context,
                    skill_entity=process_data.skill_entity,
                    actor_entity=process_data.actor_entity,
                ),
                gameplay_systems.skill_entity_utils.retrieve_skill_accessory_files(
                    context=self._context,
                    skill_entity=process_data.skill_entity,
                    actor_entity=process_data.actor_entity,
                ),
                process_data.skill_entity.get(SkillComponent).command,
            )

            create_task = AgentTask.create_with_input_only_context(
                process_data.agent, prompt
            )

            # 返回结果
            ret.append(create_task)

            ##记录下
            process_data.agent_task = create_task

        return ret

    ######################################################################################################################################################
