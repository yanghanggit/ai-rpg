from dataclasses import dataclass
from entitas import Matcher, ExecuteProcessor, Entity  # type: ignore
from my_components.action_components import (
    TagAction,
    AnnounceAction,
)
from my_components.components import (
    BaseFormComponent,
    SkillComponent,
    DestroyComponent,
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


################################################################################################################################################
def _generate_offline_prompt(actor_name: str, sentence: str) -> str:

    prompt = f"""# 注意! 全局技能系统 处于离线状态或者出错，无法使用技能，请一会再试。
## 行动内容语句({actor_name} 发起)
{sentence}
## 以上的行动将无法执行（被系统强制取消），因为技能系统处于离线状态或者出错。
"""
    return prompt


################################################################################################################################################
def _generate_failure_prompt(
    actor_name: str,
    failure_result: str,
    input_sentence: str,
    reasoning_sentence: str,
) -> str:

    prompt = f"""# 全局技能系统 推理与判断之后，判断结果为 {failure_result}

## 行动(技能)发起者: {actor_name}

## 失败类型: {failure_result}

## 原始的行动内容语句
{input_sentence}

## 系统推理后的结果
{reasoning_sentence}

## 错误分析与提示
- 请检查行动内容，必须至少有一个技能与一个目标。
- 如果 技能的释放目标 不合理会被系统拒绝。
- 虽然道具可用来配合技能使用，但使用必须合理(请注意道具的说明，使用限制等)
- 道具，技能和对象之间的关系如果不合理（违反游戏世界的运行规律与常识）。也会被系统拒绝。
"""
    return prompt


################################################################################################################################################
def _generate_success_prompt(
    actor_name: str,
    target_names: Set[str],
    success_result: str,
    input_sentence: str,
    reasoning_sentence: str,
) -> str:

    ret_prompt = f"""# 全局技能系统 推理与判断之后，判断结果为 {success_result}

## 行动(技能)发起者: {actor_name}

## 成功类型: {success_result}

## 原始行动语句(在其中可以分析出技能的目标)
{input_sentence}

## 系统推理并润色后的结果
{reasoning_sentence}"""

    return ret_prompt


################################################################################################################################################
def _generate_world_harmony_inspector_prompt(
    actor_name: str,
    actor_base_form_info: str,
    skill_prop_files: List[PropFile],
    skill_accessory_prop_files: List[PropFile],
    sentence: str,
) -> str:

    # 组织技能的提示词
    skill_prop_prompts: List[str] = []
    if len(skill_prop_files) > 0:
        for skill_file in skill_prop_files:
            skill_prop_prompts.append(generate_skill_prop_file_prompt(skill_file))
    if len(skill_prop_prompts) == 0:
        skill_prop_prompts.append("### 无任何技能")
        assert False, "技能不能为空"

    # 组织道具的提示词
    skill_accessory_prop_prompts: List[str] = []
    if len(skill_accessory_prop_files) > 0:
        for skill_accessory_prop_file in skill_accessory_prop_files:
            skill_accessory_prop_prompts.append(
                generate_skill_accessory_prop_file_prompt(skill_accessory_prop_file)
            )
    if len(skill_accessory_prop_prompts) == 0:
        skill_accessory_prop_prompts.append("### 未使用道具")

    # 组织最终的提示词
    ret_prompt = f"""# {actor_name} 准备使用技能，请你判断技能使用的合理性(是否符合游戏规则和世界观设计)。在尽量能保证游戏乐趣的情况下，来润色技能的描述。

## {actor_name} 自身信息
{actor_base_form_info}
        
## 要使用的技能
{"\n".join(skill_prop_prompts)}

## 使用技能时配置的道具
{"\n".join(skill_accessory_prop_prompts)}

## 行动内容语句(请在这段信息内提取 技能释放的目标 的信息，注意请完整引用)
{sentence}

## 判断的逻辑步骤
1. 如果 配置的道具 存在。则需要将道具与技能的信息联合起来推理。
    - 推理结果 违反了游戏规则或世界观设计。则技能释放失败。即{prompt_utils.SkillResultPromptTag.FAILURE}。
    - 推理结果合理的。则技能释放成功。即{prompt_utils.SkillResultPromptTag.SUCCESS}。如果道具对技能有增益效果，则标记为{prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}。
2. 如果 配置的道具 不存在。则继续下面的步骤。
3. 结合 {actor_name} 的自身信息。判断是否符合技能释放的条件。
    - 如果不符合。则技能释放失败。即{prompt_utils.SkillResultPromptTag.FAILURE}。
    - 如果符合。则技能释放成功。即{prompt_utils.SkillResultPromptTag.SUCCESS}。如果 {actor_name} 的自身信息，对技能有增益效果，则标记为{prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}。

## 输出格式指南

### 请根据下面的示例, 确保你的输出严格遵守相应的结构。
{{
  "{AnnounceAction.__name__}":["输出结果"],
  "{TagAction.__name__}":["{prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}或{prompt_utils.SkillResultPromptTag.SUCCESS}或{prompt_utils.SkillResultPromptTag.FAILURE}"]
}}

### 关于 {AnnounceAction.__name__} 的输出结果的规则如下
- 如果你的判断是 {prompt_utils.SkillResultPromptTag.SUCCESS} 或 {prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}。
    - 必须包含如下信息：{actor_name}的名字（技能使用者），释放的技能的描述，技能释放的目标的名字，配置的道具的信息。
    - 做出逻辑合理的句子描述（可以适当润色），来表达 {actor_name} 使用技能的使用过程。但不要判断技能命中目标之后，目标的可能反应。
    - 请注意，用第三人称的描述。  
- 如果你的判断是 {prompt_utils.SkillResultPromptTag.FAILURE}。
    - 则输出结果需要描述为：技能释放失败的原因。
    
### 注意事项
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。"""

    return ret_prompt


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
        return action.values[0]

    @property
    def inspector_content(self) -> str:
        return self._concatenate_values(AnnounceAction.__name__)

    @property
    def inspector_value(self) -> int:
        ret = 100
        ret = max(0, min(200, ret))
        return ret  # todo


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
            Matcher(all_of=[SkillComponent], none_of=[DestroyComponent])
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
    def _notify_agent_offline_event(self, process_data: InternalProcessData) -> None:

        self._context.notify_event(
            set({process_data.actor_entity}),
            AgentEvent(
                message=_generate_offline_prompt(
                    self._context.safe_get_entity_name(process_data.actor_entity),
                    process_data.skill_entity.get(SkillComponent).command,
                )
            ),
        )

    ######################################################################################################################################################
    def _notify_inspector_success_event(
        self, process_data: InternalProcessData
    ) -> None:

        self._context.notify_event(
            set({process_data.actor_entity}),
            AgentEvent(
                message=_generate_success_prompt(
                    self._context.safe_get_entity_name(process_data.actor_entity),
                    set(process_data.skill_entity.get(SkillComponent).targets),
                    process_data.plan_response.inspector_tag,
                    process_data.skill_entity.get(SkillComponent).command,
                    process_data.plan_response.inspector_content,
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
                message=_generate_failure_prompt(
                    self._context.safe_get_entity_name(process_data.actor_entity),
                    process_data.plan_response.inspector_tag,
                    process_data.skill_entity.get(SkillComponent).command,
                    process_data.plan_response.inspector_content,
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
