from dataclasses import dataclass
from entitas import Matcher, ExecuteProcessor, Entity  # type: ignore
from my_components.action_components import (
    TagAction,
    AnnounceAction,
    SkillAction,
    InspectAction,
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

    return f"""# 提示: 系统推理与判断之后，判断结果为 {inspector_tag}
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
            skill_prop_files_prompt.append(generate_skill_prop_file_prompt(skill_file))
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

    return f"""# 提示: {actor_name} 准备使用技能动作: {SkillAction.__name__}。请你作为系统，判断其技能使用的合理性（是否符合游戏规则和世界观设计）。在尽量保证游戏乐趣的前提下，润色技能使用过程的描述。

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

## 输出要求
### JSON 格式指南
请严格按照以下结构生成结果： 
{{
  "{AnnounceAction.__name__}": ["输出技能使用过程的描述"],
  "{TagAction.__name__}": ["{prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS} 或 {prompt_utils.SkillResultPromptTag.SUCCESS} 或 {prompt_utils.SkillResultPromptTag.FAILURE}"],
  "{InspectAction.__name__}": ["一个0~200的数字，代表你对结果的评估值"]
}}

### 输出示例
{
  "AnnounceAction": ["某某角色施展了炫丽的火球术，目标锁定在前方的敌人，并使用了珍贵的魔法水晶作为催化剂。"],
  "TagAction": ["<大成功>"],
  "InspectAction": ["180"]
}

### 关于 {AnnounceAction.__name__} 的输出规则
1. 成功或大成功时：
   - 必须描述：技能使用者的全名，释放的技能名称和描述，技能目标的全名，配置的道具信息。
   - 描述需用逻辑合理且生动的句子，润色后以第三人称呈现。
   - 不需涉及目标被命中后的反应，仅限于技能释放的过程。
2. 失败时：
   - 必须描述：技能释放失败的原因。

### 关于 {InspectAction.__name__} 的输出规则
- 成功/大成功/失败对应的评分范围：
  - <失败>: 0~100。
  - <成功>: 100~200。
  - 默认分值：100 为 <成功> 的基础值。

### 注意事项
- 不要使用 `json` 块封装内容。
- 输出需严格遵循结构和范围要求，不得增加多余字段。
- 在描述中加入适当润色，但保证关键信息完整。"""


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
#     # 组织最终的提示词
#     return f"""# {actor_name} 准备使用技能动作: {SkillAction.__name__}，请你作为系统来，判断其技能使用的合理性(是否符合游戏规则和世界观设计)。在尽量能保证游戏乐趣的情况下，来润色技能的描述。

# {gameplay_systems.prompt_utils.skill_action_rule_prompt()}

# ## {actor_name} 基础形态
# {actor_base_form}

# ## 使用的技能
# {"\n".join(skill_prop_files_prompt)}

# ## 配置的道具
# {"\n".join(skill_accessory_prop_files_prompt)}

# ## 技能使用指令内容
# {skill_command}

# ## 判断的逻辑步骤
# 1. 如果 配置的道具 存在。则需要将道具与技能的信息联合起来推理。
#     - 推理结果 违反了游戏规则或世界观设计。则技能释放失败。即{prompt_utils.SkillResultPromptTag.FAILURE}。
#     - 推理结果合理的。则技能释放成功。即{prompt_utils.SkillResultPromptTag.SUCCESS}。如果道具对技能有增益效果，则标记为{prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}。
# 2. 如果 配置的道具 不存在。则继续下面的步骤。
# 3. 结合 {actor_name} 的自身信息。判断是否符合技能释放的条件。
#     - 如果不符合。则技能释放失败。即{prompt_utils.SkillResultPromptTag.FAILURE}。
#     - 如果符合。则技能释放成功。即{prompt_utils.SkillResultPromptTag.SUCCESS}。如果 {actor_name} 的自身信息，对技能有增益效果，则标记为{prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}。

# ## 输出要求
# ### 输出格式指南
# 请严格遵循以下 JSON 结构示例：
# {{
#   "{AnnounceAction.__name__}":["输出结果"],
#   "{TagAction.__name__}":["{prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}或{prompt_utils.SkillResultPromptTag.SUCCESS}或{prompt_utils.SkillResultPromptTag.FAILURE}"]
#   "{InspectAction.__name__}":["一个0~200的数字，代表你对结果的评估值"]
# }}

# ### 关于 {AnnounceAction.__name__} 的输出结果的规则如下
# - 如果你的判断是 {prompt_utils.SkillResultPromptTag.SUCCESS} 或 {prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}。
#     - 必须包含如下信息：{actor_name}的全名（技能使用者），释放的技能的描述，技能释放的目标的全名，配置的道具的信息。
#     - 做出逻辑合理的句子描述（可以适当润色），来表达 {actor_name} 使用技能的使用过程。但不要判断技能命中目标之后，目标的可能反应。
#     - 用第三人称的描述。
# - 如果你的判断是 {prompt_utils.SkillResultPromptTag.FAILURE}。
#     - 则输出结果需要描述为：技能释放失败的原因。

# ### 关于 {InspectAction.__name__} 的输出结果的规则如下
# - 你需要考虑 {prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}或{prompt_utils.SkillResultPromptTag.SUCCESS}或{prompt_utils.SkillResultPromptTag.FAILURE} 的输出情况。
# - 只能输出0～200之间的数字。100为默认。为{prompt_utils.SkillResultPromptTag.SUCCESS}。
# - 100～200之间为{prompt_utils.SkillResultPromptTag.CRITICAL_SUCCESS}。
# - 0～100之间为{prompt_utils.SkillResultPromptTag.FAILURE}。

# ### 注意事项
# - 不要使用```json```来封装内容。"""
######################################################################################################################################################
######################################################################################################################################################
# """
# # 好的，我来解答一下，以便你更好的理解这段代码。

# ## 关于 代码引用的逻辑或功能：

# ### 问题：{gameplay_systems.prompt_utils.skill_action_rule_prompt()}：这个函数生成的具体内容是什么？是全局游戏规则的摘要，还是动态生成的规则集？
# 这个是我的 全局游戏规则——技能部分的摘要，我已经调整完毕，放在这里是为了让系统再次确认并理解这个规则。

# ### 问题：{prompt_utils.SkillResultPromptTag.*}：这些标签的具体值或者枚举结构是预定义的吗？
# 答：是预定义
# 源代码如下，很简单
# class SkillResultPromptTag(StrEnum):
#     SUCCESS = "<成功>"
#     CRITICAL_SUCCESS = "<大成功>"
#     FAILURE = "<失败>"

# ## 关于 输入的技能描述信息：
# 这一段你可以忽略，我已经调整好了。

# ## 关于 判断逻辑的边界条件：
# 你的问题：如果技能与角色的基础信息和配置道具均无明显匹配条件（如技能没有道具需求，但角色也没有任何增益条件），此时如何处理？直接判定失败，还是依然允许正常释放？
# 我的回答：按着正常释放计算。

# ## 关于 润色的自由度：
# 我的需求是，至少要将技能的使用过程描述清楚，即严谨的部分，谁发起，目标是谁，使用了什么道具，这些都要有。
# 艺术的部分，在此之上，你可以适当的润色，让描述更加生动。即艺术化的部分。
# """


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
