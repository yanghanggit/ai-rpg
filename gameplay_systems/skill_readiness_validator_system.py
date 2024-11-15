from dataclasses import dataclass
from entitas import Matcher, ExecuteProcessor, Entity  # type: ignore
from my_components.action_components import (
    TagAction,
    MindVoiceAction,
)
from my_components.components import (
    BaseFormComponent,
    SkillComponent,
    DestroyComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, List, Dict, Set
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
import gameplay_systems.skill_system_utils
from my_agent.lang_serve_agent import LangServeAgent


################################################################################################################################################
def _generate_skill_readiness_validator_prompt(
    actor_name: str,
    actor_base_form_info: str,
    skill_prop_files: List[PropFile],
    skill_accessory_prop_files: List[PropFile],
) -> str:

    # 组织技能的提示词
    skill_prop_prompt: List[str] = []
    if len(skill_prop_files) > 0:
        for skill_prop_file in skill_prop_files:
            assert skill_prop_file.is_skill, "不是技能文件"
            skill_prop_prompt.append(generate_skill_prop_file_prompt(skill_prop_file))

    if len(skill_prop_prompt) == 0:
        skill_prop_prompt.append("### 无任何技能")
        assert False, "技能不能为空"

    # 组织道具的提示词
    skill_accessory_prop_prompt: List[str] = []
    if len(skill_accessory_prop_files) > 0:
        for skill_accessory_prop_file in skill_accessory_prop_files:
            skill_accessory_prop_prompt.append(
                generate_skill_accessory_prop_file_prompt(skill_accessory_prop_file)
            )

    if len(skill_accessory_prop_prompt) == 0:
        skill_accessory_prop_prompt.append("### 未使用道具")

    # 组织最终的提示词
    ret_prompt = f"""# {actor_name} 计划使用技能，请做出判断是否允许使用。

## {actor_name} 自身信息
{actor_base_form_info}
        
## 要使用的技能
{"\n".join(skill_prop_prompt)}

## 使用技能时配置的道具
{"\n".join(skill_accessory_prop_prompt)}

## 判断的逻辑步骤
1. 检查 要使用的技能 的信息。结合 {actor_name} 自身信息 判断 {actor_name} 是否满足技能释放的条件。如果不能则技能释放失败。不用继续判断。
2. 检查 使用技能时配置的道具 的信息。结合 {actor_name} 自身信息 判断 {actor_name} 是否满足使用这些道具的条件。如果不能则技能释放失败。不用继续判断。
3. 分支判断 是否存在 使用技能时配置的道具。
    - 如存在。则结合 要使用的技能 与 使用技能时配置的道具 的信息进行综合半段。如果 技能对 配置的道具有明确的需求，且道具不满足，则技能释放失败。不用继续判断。
    - 如不存在。则继续下面的步骤。
4. 如果以上步骤都通过，则技能释放成功。

## 输出格式指南

### 请根据下面的示例, 确保你的输出严格遵守相应的结构。
{{
  "{MindVoiceAction.__name__}":["输入你的最终判断结果，技能是否可以使用成功或失败，并附带原因"],
  "{TagAction.__name__}":["Yes/No"(即技能是否可以使用成功或失败)"]
}}

### 注意事项
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。"""

    return ret_prompt


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################


@final
class InternalPlanResponse(AgentPlanResponse):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def is_skill_ready(self) -> bool:
        return self._parse_boolean(TagAction.__name__)


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
@dataclass
class InternalProcessData:
    actor_entity: Entity
    skill_entity: Entity
    agent: LangServeAgent
    agent_task: AgentTask


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################


@final
class SkillReadinessValidatorSystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ######################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        # 只关注技能
        skill_entities = self._context.get_group(
            Matcher(all_of=[SkillComponent], none_of=[DestroyComponent])
        ).entities.copy()

        # 组成成方便的数据结构
        internal_process_data = self._initialize_internal_process_data(skill_entities)

        # 核心执行
        await self._validate_skill_readiness(internal_process_data)

    ######################################################################################################################################################
    def _initialize_internal_process_data(
        self, skill_entities: Set[Entity]
    ) -> List[InternalProcessData]:

        ret: List[InternalProcessData] = []
        for skill_entity in skill_entities:
            skill_comp = skill_entity.get(SkillComponent)

            actor_entity = self._context.get_actor_entity(skill_comp.name)
            assert (
                actor_entity is not None
            ), f"actor_entity {skill_comp.name} not found."
            if actor_entity is None:
                logger.debug(f"actor_entity {skill_comp.name} not found.")
                continue

            actor_name = self._context.safe_get_entity_name(actor_entity)
            agent = self._context.agent_system.get_agent(actor_name)
            assert agent is not None, f"agent {actor_name} not found."
            if agent is None:
                continue

            ret.append(
                InternalProcessData(
                    actor_entity=actor_entity,
                    skill_entity=skill_entity,
                    agent=agent,
                    agent_task=AgentTask.create_without_context(agent=agent, prompt=""),
                )
            )

        return ret

    ######################################################################################################################################################
    async def _validate_skill_readiness(
        self, internal_process_data: List[InternalProcessData]
    ) -> None:

        if len(internal_process_data) == 0:
            return

        agent_tasks = self._generate_agent_tasks(internal_process_data)
        assert len(agent_tasks) > 0, "agent_tasks is empty."
        if len(agent_tasks) == 0:
            self._clear(internal_process_data)
            return

        responses = await AgentTask.gather([task for task in agent_tasks.values()])
        if len(responses) == 0:
            logger.debug(f"phase1_response is None.")
            self._clear(internal_process_data)
            return

        self._process_agent_tasks(internal_process_data)

    ######################################################################################################################################################
    def _process_agent_tasks(
        self, internal_process_data: List[InternalProcessData]
    ) -> None:

        for process_data in internal_process_data:

            agent_task = process_data.agent_task
            assert agent_task is not None, "agent_task is None."

            if not self._is_skill_ready(agent_task):
                gameplay_systems.skill_system_utils.destroy_skill_entity(
                    process_data.skill_entity
                )
                continue

    ######################################################################################################################################################
    def _is_skill_ready(self, agent_task: AgentTask) -> bool:
        if agent_task.response_content == "":
            return False

        return InternalPlanResponse(
            agent_task.agent_name, agent_task.response_content
        ).is_skill_ready

    ######################################################################################################################################################
    def _clear(self, internal_process_data: List[InternalProcessData]) -> None:
        for process_data in internal_process_data:
            assert process_data.skill_entity is not None, "skill_entity is None."
            gameplay_systems.skill_system_utils.destroy_skill_entity(
                process_data.skill_entity
            )

    ######################################################################################################################################################
    def _generate_agent_tasks(
        self, internal_process_data: List[InternalProcessData]
    ) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        for process_data in internal_process_data:

            assert process_data.actor_entity is not None, "actor_entity is None."
            assert process_data.skill_entity is not None, "skill_entity is None."
            assert process_data.agent is not None, "agent is None."

            skill_readiness_prompt = _generate_skill_readiness_validator_prompt(
                process_data.agent._name,
                process_data.actor_entity.get(BaseFormComponent).base_form,
                gameplay_systems.skill_system_utils.parse_skill_prop_files(
                    context=self._context,
                    skill_entity=process_data.skill_entity,
                    actor_entity=process_data.actor_entity,
                ),
                gameplay_systems.skill_system_utils.retrieve_skill_accessory_files(
                    context=self._context,
                    skill_entity=process_data.skill_entity,
                    actor_entity=process_data.actor_entity,
                ),
            )

            process_data.agent_task = ret[process_data.agent._name] = (
                AgentTask.create_with_full_context(
                    process_data.agent,
                    prompt_utils.replace_you(
                        skill_readiness_prompt, process_data.agent._name
                    ),
                )
            )

        return ret

    ######################################################################################################################################################
