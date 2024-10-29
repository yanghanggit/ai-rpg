from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from my_components.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    SkillUsePropAction,
    TagAction,
    MindVoiceAction,
    WorldSkillSystemRuleAction,
)
from my_components.components import (
    BodyComponent,
    ActorComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, List, Set, Dict, Any
from loguru import logger
from extended_systems.files_def import PropFile
import gameplay_systems.public_builtin_prompt as public_builtin_prompt
from my_agent.agent_task import AgentTask
from my_agent.agent_plan import AgentPlanResponse
from rpg_game.rpg_game import RPGGame


################################################################################################################################################


def _generate_skill_usage_reasoning_prompt(
    actor_name: str,
    actor_body_info: str,
    skill_files: List[PropFile],
    prop_files: List[PropFile],
) -> str:

    skills_prompt: List[str] = []
    if len(skill_files) > 0:
        for skill_file in skill_files:
            skills_prompt.append(
                public_builtin_prompt.generate_prop_prompt(
                    skill_file, description_prompt=True, appearance_prompt=False
                )
            )
    else:

        skills_prompt.append("- 无任何技能。")
        assert False, "技能不能为空"

    props_prompt: List[str] = []
    if len(prop_files) > 0:
        for prop_file in prop_files:
            props_prompt.append(
                public_builtin_prompt.generate_prop_prompt(
                    prop_file, description_prompt=True, appearance_prompt=False
                )
            )
    else:
        props_prompt.append("- 无任何道具。")

    ret_prompt = f"""# {actor_name} 计划使用技能，请做出判断是否允许使用。

## {actor_name} 自身信息
{actor_body_info}
        
## 要使用的技能
{"\n".join(skills_prompt)}

## 使用技能时配置的道具
{"\n".join(props_prompt)}

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


@final
class SelfUsageCheckResponse(AgentPlanResponse):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def boolean_value(self) -> bool:
        return self._parse_boolean(TagAction.__name__)

    @property
    def out_come(self) -> str:
        return self._concatenate_values(MindVoiceAction.__name__)


@final
class SelfSkillUsageCheckSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)

        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._react_entities_copy: List[Entity] = []

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SkillAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(SkillAction)
            and entity.has(SkillTargetAction)
            and entity.has(BehaviorAction)
            and entity.has(ActorComponent)
        )

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        self._react_entities_copy = entities.copy()

    ######################################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        await self._execute(self._react_entities_copy)
        self._react_entities_copy.clear()

    ######################################################################################################################################################
    async def _execute(self, entities: List[Entity]) -> None:

        if len(entities) == 0:
            return

        tasks = self.create_tasks(entities)
        if len(tasks) == 0:
            self.on_remove_all(entities)
            return

        responses = await AgentTask.gather([task for task in tasks.values()])
        if len(responses) == 0:
            logger.debug(f"phase1_response is None.")
            self.on_remove_all(entities)
            return

        self.handle_tasks(tasks)

    ######################################################################################################################################################
    def handle_tasks(self, tasks: Dict[str, AgentTask]) -> None:

        for agent_name, task in tasks.items():

            actor_entity = self._context.get_actor_entity(agent_name)
            if actor_entity is None:
                continue

            if task.response_content == "":
                # 没有回答，直接清除所有的action
                self.on_remove_action(actor_entity)
                continue

            response_plan = SelfUsageCheckResponse(agent_name, task.response_content)

            if not response_plan.boolean_value:
                # 失败就不用继续了，直接清除所有的action
                self.on_remove_action(actor_entity)

    ######################################################################################################################################################
    def on_remove_action(
        self,
        entity: Entity,
        action_comps: Set[type[Any]] = {
            BehaviorAction,
            SkillAction,
            SkillTargetAction,
            SkillUsePropAction,
            WorldSkillSystemRuleAction,
        },
    ) -> None:

        for action_comp in action_comps:
            if entity.has(action_comp):
                entity.remove(action_comp)

    ######################################################################################################################################################
    def on_remove_all(self, entities: List[Entity]) -> None:
        for entity in entities:
            self.on_remove_action(entity)

    ######################################################################################################################################################
    def extract_skill_files(self, entity: Entity) -> List[PropFile]:
        assert entity.has(SkillAction) and entity.has(SkillTargetAction)

        ret: List[PropFile] = []

        safe_name = self._context.safe_get_entity_name(entity)
        skill_action = entity.get(SkillAction)
        for skill_name in skill_action.values:

            skill_file = self._context._file_system.get_file(
                PropFile, safe_name, skill_name
            )
            if skill_file is None or not skill_file.is_skill:
                continue

            ret.append(skill_file)

        return ret

    ######################################################################################################################################################
    def extract_body_info(self, entity: Entity) -> str:
        if not entity.has(BodyComponent):
            return ""
        return str(entity.get(BodyComponent).body)

    ######################################################################################################################################################
    def extract_prop_files(self, entity: Entity) -> List[PropFile]:
        if not entity.has(SkillUsePropAction):
            return []

        safe_name = self._context.safe_get_entity_name(entity)
        prop_action = entity.get(SkillUsePropAction)
        ret: List[PropFile] = []
        for prop_name in prop_action.values:
            prop_file = self._context._file_system.get_file(
                PropFile, safe_name, prop_name
            )
            if prop_file is None:
                continue
            ret.append(prop_file)

        return ret

    ######################################################################################################################################################
    def create_tasks(self, entities: List[Entity]) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        for entity in entities:

            agent_name = self._context.safe_get_entity_name(entity)

            agent = self._context._langserve_agent_system.get_agent(agent_name)
            if agent is None:
                continue

            prompt = _generate_skill_usage_reasoning_prompt(
                agent_name,
                self.extract_body_info(entity),
                self.extract_skill_files(entity),
                self.extract_prop_files(entity),
            )

            # 会添加上下文的！！！！
            ret[agent._name] = AgentTask.create(
                agent,
                public_builtin_prompt.replace_you(prompt, agent_name),
            )

        return ret

    ######################################################################################################################################################
