from dataclasses import dataclass
from entitas import Matcher, ExecuteProcessor, Entity  # type: ignore
from my_components.action_components import (
    TagAction,
    MindVoiceAction,
)
from my_components.components import (
    BodyComponent,
    SkillComponent,
    DestroyComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, List, Dict, Set, Optional
from loguru import logger
from extended_systems.prop_file import (
    PropFile,
    generate_skill_prop_file_prompt,
    generate_skill_accessory_prop_file_prompt,
)
import gameplay_systems.builtin_prompt_util as builtin_prompt_util
from my_agent.agent_task import AgentTask
from my_agent.agent_plan import AgentPlanResponse
from rpg_game.rpg_game import RPGGame
import gameplay_systems.skill_system_utils


################################################################################################################################################
def _generate_skill_readiness_validator_prompt(
    actor_name: str,
    actor_body_info: str,
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
{actor_body_info}
        
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
    def boolean_value(self) -> bool:
        return self._parse_boolean(TagAction.__name__)

    @property
    def out_come(self) -> str:
        return self._concatenate_values(MindVoiceAction.__name__)


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
@dataclass
class InternalProcessor:
    actor_entity: Entity
    skill_entity: Entity
    agent_task: Optional[AgentTask]


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
        skill_processors = self._initialize_processors(skill_entities)

        # 核心执行
        await self._validate_skill_readiness(skill_processors)

    ######################################################################################################################################################
    def _initialize_processors(
        self, skill_entities: Set[Entity]
    ) -> List[InternalProcessor]:
        ret: List[InternalProcessor] = []
        for skill_entity in skill_entities:
            skill_comp = skill_entity.get(SkillComponent)
            actor_entity = self._context.get_actor_entity(skill_comp.name)
            assert (
                actor_entity is not None
            ), f"actor_entity {skill_comp.name} not found."
            ret.append(InternalProcessor(actor_entity, skill_entity, None))
        return ret

    ######################################################################################################################################################
    async def _validate_skill_readiness(
        self, skill_processors: List[InternalProcessor]
    ) -> None:

        if len(skill_processors) == 0:
            return

        tasks = self._generate_agent_tasks(skill_processors)
        if len(tasks) == 0:
            self._clear(skill_processors)
            return

        responses = await AgentTask.gather([task for task in tasks.values()])
        if len(responses) == 0:
            logger.debug(f"phase1_response is None.")
            self._clear(skill_processors)
            return

        self._process_agent_tasks(skill_processors)

    ######################################################################################################################################################
    def _process_agent_tasks(self, skill_processors: List[InternalProcessor]) -> None:

        for skill_processor in skill_processors:

            agent_task = skill_processor.agent_task
            if agent_task is None:
                gameplay_systems.skill_system_utils.destroy_skill_entity(
                    skill_processor.skill_entity
                )
                continue

            assert skill_processor.skill_entity is not None, "skill_entity is None."
            if agent_task.response_content == "":
                gameplay_systems.skill_system_utils.destroy_skill_entity(
                    skill_processor.skill_entity
                )
                continue

            skill_readiness_response = InternalPlanResponse(
                agent_task.agent_name, agent_task.response_content
            )

            if not skill_readiness_response.boolean_value:
                # 删除
                gameplay_systems.skill_system_utils.destroy_skill_entity(
                    skill_processor.skill_entity
                )

    ######################################################################################################################################################
    def _clear(self, skill_processors: List[InternalProcessor]) -> None:
        for skill_processor in skill_processors:
            assert skill_processor.skill_entity is not None, "skill_entity is None."
            gameplay_systems.skill_system_utils.destroy_skill_entity(
                skill_processor.skill_entity
            )

    ######################################################################################################################################################
    def _generate_agent_tasks(
        self, skill_processors: List[InternalProcessor]
    ) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        for skill_processor in skill_processors:

            if skill_processor.actor_entity is None:
                assert False, "actor_entity is None."
                continue

            agent_name = self._context.safe_get_entity_name(
                skill_processor.actor_entity
            )

            agent = self._context.agent_system.get_agent(agent_name)
            if agent is None:
                assert False, f"agent {agent_name} not found."
                continue

            prompt = _generate_skill_readiness_validator_prompt(
                agent_name,
                skill_processor.actor_entity.get(BodyComponent).body,
                gameplay_systems.skill_system_utils.parse_skill_prop_files(
                    context=self._context,
                    skill_entity=skill_processor.skill_entity,
                    actor_entity=skill_processor.actor_entity,
                ),
                gameplay_systems.skill_system_utils.retrieve_skill_accessory_files(
                    context=self._context,
                    skill_entity=skill_processor.skill_entity,
                    actor_entity=skill_processor.actor_entity,
                ),
            )

            ret[agent_name] = AgentTask.create(
                agent,
                builtin_prompt_util.replace_you(prompt, agent_name),
            )

            assert skill_processor.agent_task is None, "agent_task is not None."
            skill_processor.agent_task = ret[agent_name]

        return ret

    ######################################################################################################################################################
