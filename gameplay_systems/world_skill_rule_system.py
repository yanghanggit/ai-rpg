from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    SkillUsePropAction,
    TagAction,
    BroadcastAction,
    WorldSkillSystemRuleAction,
)
from gameplay_systems.components import (
    BodyComponent,
    ActorComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, List, Set, Dict, Any
from loguru import logger
from extended_systems.files_def import PropFile
import gameplay_systems.public_builtin_prompt as public_builtin_prompt
from my_agent.agent_task import AgentTask
from my_agent.agent_plan import AgentPlanResponse
from rpg_game.rpg_game import RPGGame
import extended_systems.file_system_helper
from gameplay_systems.gameplay_event import AgentEvent


################################################################################################################################################
def _generate_offline_prompt(actor_name: str, behavior_sentence: str) -> str:

    prompt = f"""# 注意! 全局技能系统 处于离线状态或者出错，无法使用技能，请一会再试。
## 行动内容语句({actor_name} 发起)
{behavior_sentence}
## 以上的行动将无法执行（被系统强制取消），因为技能系统处于离线状态或者出错。
"""
    return prompt


################################################################################################################################################
def _generate_rule_failure_prompt(
    actor_name: str,
    failure_result: str,
    input_behavior_sentence: str,
    reasoning_sentence: str,
) -> str:

    prompt = f"""# 全局技能系统 推理与判断之后，判断结果为 {failure_result}

## 行动(技能)发起者: {actor_name}

## 失败类型: {failure_result}

## 原始的行动内容语句
{input_behavior_sentence}

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


def _generate_rule_success_prompt(
    actor_name: str,
    target_names: Set[str],
    success_result: str,
    input_behavior_sentence: str,
    reasoning_sentence: str,
) -> str:

    ret_prompt = f"""# 全局技能系统 推理与判断之后，判断结果为 {success_result}

## 行动(技能)发起者: {actor_name}

## 成功类型: {success_result}

## 原始行动语句(在其中可以分析出技能的目标)
{input_behavior_sentence}

## 系统推理并润色后的结果
{reasoning_sentence}"""

    return ret_prompt


################################################################################################################################################


def _generate_rule_prompt(
    actor_name: str,
    actor_body_info: str,
    skill_files: List[PropFile],
    prop_files: List[PropFile],
    behavior_sentence: str,
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

    ret_prompt = f"""# {actor_name} 准备使用技能，请你判断技能使用的合理性(是否符合游戏规则和世界观设计)。在尽量能保证游戏乐趣的情况下，来润色技能的描述。

## {actor_name} 自身信息
{actor_body_info}
        
## 要使用的技能
{"\n".join(skills_prompt)}

## 使用技能时配置的道具
{"\n".join(props_prompt)}

## 行动内容语句(请在这段信息内提取 技能释放的目标 的信息，注意请完整引用)
{behavior_sentence}

## 判断的逻辑步骤
1. 如果 配置的道具 存在。则需要将道具与技能的信息联合起来推理。
    - 推理结果 违反了游戏规则或世界观设计。则技能释放失败。即{public_builtin_prompt.ConstantPrompt.FAILURE}。
    - 推理结果合理的。则技能释放成功。即{public_builtin_prompt.ConstantPrompt.SUCCESS}。如果道具对技能有增益效果，则标记为{public_builtin_prompt.ConstantPrompt.CRITICAL_SUCCESS}。
2. 如果 配置的道具 不存在。则继续下面的步骤。
3. 结合 {actor_name} 的自身信息。判断是否符合技能释放的条件。
    - 如果不符合。则技能释放失败。即{public_builtin_prompt.ConstantPrompt.FAILURE}。
    - 如果符合。则技能释放成功。即{public_builtin_prompt.ConstantPrompt.SUCCESS}。如果 {actor_name} 的自身信息，对技能有增益效果，则标记为{public_builtin_prompt.ConstantPrompt.CRITICAL_SUCCESS}。

## 输出格式指南

### 请根据下面的示例, 确保你的输出严格遵守相应的结构。
{{
  "{BroadcastAction.__name__}":["输出结果"],
  "{TagAction.__name__}":["{public_builtin_prompt.ConstantPrompt.CRITICAL_SUCCESS}或{public_builtin_prompt.ConstantPrompt.SUCCESS}或{public_builtin_prompt.ConstantPrompt.FAILURE}"]
}}

### 关于 {BroadcastAction.__name__} 的输出结果的规则如下
- 如果你的判断是 {public_builtin_prompt.ConstantPrompt.SUCCESS} 或 {public_builtin_prompt.ConstantPrompt.CRITICAL_SUCCESS}。
    - 必须包含如下信息：{actor_name}的名字（技能使用者），释放的技能的描述，技能释放的目标的名字，配置的道具的信息。
    - 做出逻辑合理的句子描述（可以适当润色），来表达 {actor_name} 使用技能的使用过程。但不要判断技能命中目标之后，目标的可能反应。
    - 请注意，用第三人称的描述。  
- 如果你的判断是 {public_builtin_prompt.ConstantPrompt.FAILURE}。
    - 则输出结果需要描述为：技能释放失败的原因。
    
### 注意事项
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。"""

    return ret_prompt


######################################################################################################################################################
class WorldSkillRuleResponse(AgentPlanResponse):

    OPTION_PARAM_NAME: str = "actor_name"

    def __init__(self, name: str, input_str: str, task: AgentTask) -> None:
        super().__init__(name, input_str)
        self._task: AgentTask = task

    @property
    def result(self) -> str:
        action = self.get_action(TagAction.__name__)
        if action is None or len(action.values) == 0:
            return public_builtin_prompt.ConstantPrompt.FAILURE
        return action.values[0]

    @property
    def out_come(self) -> str:
        return self._concatenate_values(BroadcastAction.__name__)


######################################################################################################################################################


class WorldSkillRuleSystem(ReactiveProcessor):

    def __init__(
        self, context: RPGEntitasContext, rpg_game: RPGGame, system_name: str
    ) -> None:
        super().__init__(context)

        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._system_name: str = system_name
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

        if (
            self._context.get_world_entity(self._system_name) is not None
            and len(self._react_entities_copy) > 0
        ):
            await self._execute(self._react_entities_copy, self._system_name)

        self._react_entities_copy.clear()

    ######################################################################################################################################################
    async def _execute(
        self, entities: List[Entity], world_skill_system_name: str
    ) -> None:

        if len(entities) == 0:
            return

        # 第二个大阶段，全局技能系统检查技能组合是否合法
        tasks = self.create_tasks(entities, world_skill_system_name)
        if len(tasks) == 0:
            self.on_remove_all(entities)
            return

        responses = await AgentTask.gather(tasks)
        if len(responses) == 0:
            self.on_remove_all(entities)
            return

        response_plans = self.create_responses(tasks)
        self.handle_responses(response_plans)

    ######################################################################################################################################################
    def handle_responses(
        self, response_plans: Dict[str, WorldSkillRuleResponse]
    ) -> None:

        for actor_name, response_plan in response_plans.items():
            actor_entity = self._context.get_actor_entity(actor_name)
            if actor_entity is None:
                continue

            if response_plan._task.response_content == "":
                self.on_world_skill_system_off_line_event(actor_entity)
                continue

            match (response_plan.result):
                case public_builtin_prompt.ConstantPrompt.FAILURE:
                    self.on_world_skill_system_rule_fail_event(
                        actor_entity, response_plan
                    )
                    self.on_remove_action(actor_entity)
                case public_builtin_prompt.ConstantPrompt.SUCCESS:
                    self.on_world_skill_system_rule_success_event(
                        actor_entity, response_plan
                    )
                    self.add_world_skill_system_rule_action(actor_entity, response_plan)
                    self.consume_consumable_props(actor_entity)

                case public_builtin_prompt.ConstantPrompt.CRITICAL_SUCCESS:
                    self.on_world_skill_system_rule_success_event(
                        actor_entity, response_plan
                    )
                    self.add_world_skill_system_rule_action(actor_entity, response_plan)
                    self.consume_consumable_props(actor_entity)

                case _:
                    logger.error(f"Unknown tag: {response_plan.result}")

    ######################################################################################################################################################
    def consume_consumable_props(self, entity: Entity) -> None:
        prop_files = self.extract_prop_files(entity)
        for prop_file in prop_files:
            if prop_file.is_consumable_item:
                extended_systems.file_system_helper.consume_consumable(
                    self._context._file_system, prop_file
                )

    ######################################################################################################################################################
    def add_world_skill_system_rule_action(
        self, entity: Entity, response_plan: WorldSkillRuleResponse
    ) -> None:

        actor_name = self._context.safe_get_entity_name(entity)
        entity.replace(
            WorldSkillSystemRuleAction,
            actor_name,
            [response_plan.result, response_plan.out_come],
        )

    ######################################################################################################################################################
    def create_responses(
        self, world_system_agent_tasks: List[AgentTask]
    ) -> Dict[str, WorldSkillRuleResponse]:

        ret: Dict[str, WorldSkillRuleResponse] = {}

        for world_system_agent_task in world_system_agent_tasks:

            actor_name = world_system_agent_task._extend_params.get(
                WorldSkillRuleResponse.OPTION_PARAM_NAME, ""
            )

            entity = self._context.get_actor_entity(actor_name)
            if entity is None:
                continue

            ret[actor_name] = WorldSkillRuleResponse(
                world_system_agent_task.agent_name,
                world_system_agent_task.response_content,
                world_system_agent_task,
            )

        return ret

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

    def extract_behavior_sentence(self, entity: Entity) -> str:
        behavior_action = entity.get(BehaviorAction)
        if behavior_action is None or len(behavior_action.values) == 0:
            return ""
        return behavior_action.values[0]

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
        skill_use_prop_action = entity.get(SkillUsePropAction)

        ret: List[PropFile] = []
        for prop_name in skill_use_prop_action.values:
            prop_file = self._context._file_system.get_file(
                PropFile, safe_name, prop_name
            )
            if prop_file is None:
                continue
            ret.append(prop_file)

        return ret

    ######################################################################################################################################################
    def on_world_skill_system_off_line_event(self, entity: Entity) -> None:

        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message_content=_generate_offline_prompt(
                    self._context.safe_get_entity_name(entity),
                    self.extract_behavior_sentence(entity),
                )
            ),
        )

    ######################################################################################################################################################
    def on_world_skill_system_rule_success_event(
        self, entity: Entity, world_response_plan: WorldSkillRuleResponse
    ) -> None:

        target_entities = self.extract_targets(entity)
        target_names: Set[str] = set()
        for target_entity in target_entities:
            target_names.add(self._context.safe_get_entity_name(target_entity))

        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message_content=_generate_rule_success_prompt(
                    self._context.safe_get_entity_name(entity),
                    target_names,
                    world_response_plan.result,
                    self.extract_behavior_sentence(entity),
                    world_response_plan.out_come,
                )
            ),
        )

    ######################################################################################################################################################
    def on_world_skill_system_rule_fail_event(
        self, entity: Entity, world_response_plan: WorldSkillRuleResponse
    ) -> None:

        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message_content=_generate_rule_failure_prompt(
                    self._context.safe_get_entity_name(entity),
                    world_response_plan.result,
                    self.extract_behavior_sentence(entity),
                    world_response_plan.out_come,
                )
            ),
        )

    ######################################################################################################################################################
    def create_tasks(
        self, actor_entities: List[Entity], world_skill_system_name: str
    ) -> List[AgentTask]:

        ret: List[AgentTask] = []

        world_system_agent = self._context._langserve_agent_system.get_agent(
            world_skill_system_name
        )
        if world_system_agent is None:
            return ret

        for actor_entity in actor_entities:

            prompt = _generate_rule_prompt(
                self._context.safe_get_entity_name(actor_entity),
                self.extract_body_info(actor_entity),
                self.extract_skill_files(actor_entity),
                self.extract_prop_files(actor_entity),
                self.extract_behavior_sentence(actor_entity),
            )

            world_system_agent_task = AgentTask.create_process_context_without_saving(
                world_system_agent, prompt
            )

            world_system_agent_task._extend_params.setdefault(
                WorldSkillRuleResponse.OPTION_PARAM_NAME,
                self._context.safe_get_entity_name(actor_entity),
            )
            ret.append(world_system_agent_task)

        return ret

    ######################################################################################################################################################
    def extract_targets(self, entity: Entity) -> Set[Entity]:
        assert entity.has(SkillTargetAction)

        targets = set()
        for target_name in entity.get(SkillTargetAction).values:
            target = self._context.get_entity_by_name(target_name)
            if target is not None:
                targets.add(target)

        return targets

    ######################################################################################################################################################
